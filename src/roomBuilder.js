// Shared room-mesh construction, extracted from the single-room POC
// (PrimaryRoomPOC.jsx) so the multi-room Continuum scene renders every room
// with the exact same walls/floor/ceiling/door/window approach - not a
// re-implementation that could quietly diverge. Pure refactor: behavior for
// the single-room POC is unchanged (see PrimaryRoomPOC.jsx, which now
// imports from here instead of defining this logic locally).
import * as THREE from "three";

// Placeholder wall thickness (ft) - not detected/measured data, an
// explicitly invented constant for this proof of concept only (the backend
// geometry has no thickness field at all).
export const WALL_THICKNESS_FT = 0.5;
const CORNER_EXT = WALL_THICKNESS_FT / 2; // half-thickness corner extension so adjacent walls meet cleanly

// Plan-local (x, y) -> three.js (x, z). y (plan depth) becomes z; vertical
// (three.js y) is handled separately via height_ft, never taken from the
// wall endpoints' 3rd coordinate (which is always 0 in the source data).
export function toSceneXZ([x, y]) {
  return [x, y];
}

// Splits one wall's face (u = distance along the wall, v = height) into
// rectangular box segments that fill the wall MINUS a single opening, so a
// door/window becomes an actual hole rather than a mesh overlapping empty
// space. `full.u0/u1` are already extended half a wall-thickness past each
// end so adjacent walls' boxes overlap exactly at the corner instead of
// leaving a gap or a doubled edge.
export function wallSegments(length, wallHeight, opening) {
  const full = { u0: -CORNER_EXT, u1: length + CORNER_EXT, v0: 0, v1: wallHeight };
  if (!opening) return [full];

  const { u0: ou0, u1: ou1, v0: ov0, v1: ov1 } = opening;
  const segs = [];
  if (ou0 > full.u0) segs.push({ u0: full.u0, u1: ou0, v0: full.v0, v1: full.v1 }); // left of opening
  if (ou1 < full.u1) segs.push({ u0: ou1, u1: full.u1, v0: full.v0, v1: full.v1 }); // right of opening
  if (ov0 > full.v0) segs.push({ u0: ou0, u1: ou1, v0: full.v0, v1: ov0 }); // sill/below opening
  if (ov1 < full.v1) segs.push({ u0: ou0, u1: ou1, v0: ov1, v1: full.v1 }); // header/above opening
  return segs;
}

// One shared material set. Callers may pass the same instance to every
// room for consistency/efficiency; buildRoomGroup() always clones the floor
// material per room so a single room's floor can be recolored (selection
// highlight) without affecting every other room sharing the same base set.
export function createRoomMaterials() {
  return {
    floor: new THREE.MeshStandardMaterial({ color: 0xb9ada0, roughness: 0.9, side: THREE.DoubleSide }),
    ceiling: new THREE.MeshStandardMaterial({ color: 0xf7f5f0, roughness: 0.95, side: THREE.DoubleSide }),
    wall: new THREE.MeshStandardMaterial({ color: 0xd8dade, roughness: 0.85 }),
    door: new THREE.MeshStandardMaterial({ color: 0x6b4a32, roughness: 0.6 }),
    glass: new THREE.MeshStandardMaterial({
      color: 0xbfe3f0, roughness: 0.05, metalness: 0.1, transparent: true, opacity: 0.35, side: THREE.DoubleSide,
    }),
  };
}

// Builds one room's meshes in LOCAL room coordinates (the room's own (0,0)
// origin - not globally placed). Callers position/offset the returned group
// to place it in a shared scene (see ContinuumUnitPOC.jsx). `roomId` is
// stamped onto every mesh's userData for click-to-select raycasting.
export function buildRoomGroup(room, materials, roomId) {
  const group = new THREE.Group();

  const xs = room.boundary.map((p) => p[0]);
  const ys = room.boundary.map((p) => p[1]);
  const width = Math.max(...xs) - Math.min(...xs);
  const depth = Math.max(...ys) - Math.min(...ys);
  const height = room.ceiling_ft;

  // Cloned per room so selection highlighting can recolor just this one
  // room's floor without affecting the shared instance other rooms use.
  const floorMat = materials.floor.clone();

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(width / 2, 0, depth / 2);
  floor.userData.roomId = roomId;
  floor.userData.isFloor = true;
  group.add(floor);

  const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(width, depth), materials.ceiling);
  ceiling.rotation.x = Math.PI / 2;
  ceiling.position.set(width / 2, height, depth / 2);
  ceiling.userData.roomId = roomId;
  group.add(ceiling);

  const door = room.doors?.[0];
  const win = room.windows?.[0];

  for (const wall of room.walls) {
    const [ax, ay] = toSceneXZ(wall.a);
    const [bx, by] = toSceneXZ(wall.b);
    const length = Math.hypot(bx - ax, by - ay);
    const angle = Math.atan2(by - ay, bx - ax);
    const wallHeight = wall.height_ft ?? height;
    const dir = { x: (bx - ax) / length, z: (by - ay) / length };

    const addSeg = (seg, material, thickness = WALL_THICKNESS_FT) => {
      const centerU = (seg.u0 + seg.u1) / 2;
      const centerV = (seg.v0 + seg.v1) / 2;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(seg.u1 - seg.u0, seg.v1 - seg.v0, thickness),
        material,
      );
      mesh.position.set(ax + dir.x * centerU, centerV, ay + dir.z * centerU);
      mesh.rotation.y = -angle;
      mesh.userData.roomId = roomId;
      group.add(mesh);
      return mesh;
    };

    let opening = null;
    let openingMaterial = null;
    let openingThicknessFactor = 1;
    if (door && wall.id === door.wall) {
      opening = {
        u0: door.offset_ft - door.width_ft / 2, u1: door.offset_ft + door.width_ft / 2,
        v0: 0, v1: door.height_ft,
      };
      openingMaterial = materials.door;
      openingThicknessFactor = 0.7; // sits slightly recessed within the wall
    } else if (win && wall.id === win.wall) {
      opening = {
        u0: win.offset_ft - win.width_ft / 2, u1: win.offset_ft + win.width_ft / 2,
        v0: win.sill_height_ft, v1: win.head_height_ft,
      };
      openingMaterial = materials.glass;
      openingThicknessFactor = 0.3; // thin pane
    }

    for (const seg of wallSegments(length, wallHeight, opening)) {
      const mesh = addSeg(seg, materials.wall);
      mesh.name = wall.id;
    }
    if (opening) {
      const filler = addSeg(opening, openingMaterial, WALL_THICKNESS_FT * openingThicknessFactor);
      filler.name = `${wall.id}_${openingMaterial === materials.door ? "door" : "window"}`;
    }
  }

  return { group, width, depth, height, floorMat };
}
