import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CONTINUUM_ROOMS } from "./data/continuumRooms.js";
import { buildRoomGroup, createRoomMaterials } from "./roomBuilder.js";

const EYE_HEIGHT_FT = 5.5;
const SELECTED_FLOOR_COLOR = 0xd6b46a;
const CLICK_MAX_MOVE_PX = 6;
const CLICK_MAX_MS = 350;

// Global unit bounding box across every placed room, used to frame the
// overview camera/grid without hardcoding numbers that would go stale if
// the data changes.
function computeUnitBounds(rooms) {
  let minX = Infinity, minZ = Infinity, maxX = -Infinity, maxZ = -Infinity;
  for (const r of rooms) {
    const [ox, oz] = r.global_origin_ft;
    minX = Math.min(minX, ox);
    minZ = Math.min(minZ, oz);
    maxX = Math.max(maxX, ox + r.width_ft);
    maxZ = Math.max(maxZ, oz + r.depth_ft);
  }
  return { minX, minZ, maxX, maxZ, width: maxX - minX, depth: maxZ - minZ,
           centerX: (minX + maxX) / 2, centerZ: (minZ + maxZ) / 2 };
}

export default function ContinuumUnitPOC() {
  const mountRef = useRef(null);
  const apiRef = useRef(null); // { selectRoom(id) } exposed to the room-list UI
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const mount = mountRef.current;
    const rooms = CONTINUUM_ROOMS;
    const bounds = computeUnitBounds(rooms);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111418);

    const camera = new THREE.PerspectiveCamera(50, mount.clientWidth / mount.clientHeight, 0.1, 1000);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    // Build every room, in its own local coordinates, then offset the
    // returned group by its global_origin_ft to place it in the shared
    // scene - the ONLY thing that changes vs. the single-room POC is this
    // per-room translation; wall/floor/ceiling/door/window construction
    // itself is the exact same shared roomBuilder.js code.
    const materials = createRoomMaterials();
    const placed = new Map(); // roomId -> { group, width, depth, floorMat, centerX, centerZ }
    const selectableMeshes = [];

    for (const room of rooms) {
      const { group, width, depth, floorMat } = buildRoomGroup(room, materials, room.room_id);
      const [ox, oz] = room.global_origin_ft;
      group.position.set(ox, 0, oz);
      scene.add(group);
      group.traverse((obj) => {
        if (obj.isMesh) selectableMeshes.push(obj);
      });
      placed.set(room.room_id, {
        group, width, depth, floorMat,
        centerX: ox + width / 2, centerZ: oz + depth / 2,
      });
    }

    // Lighting: same approach as the single-room POC (hemisphere + ambient
    // fill + directional sun + an interior point light), scaled/positioned
    // to the whole unit's footprint instead of one room.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x555045, 1.0));
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const sun = new THREE.DirectionalLight(0xfff4e0, 0.9);
    sun.position.set(bounds.maxX + 20, 40, bounds.centerZ);
    scene.add(sun);
    // One fixed room light isn't enough to cover ~40x35ft of floor plan -
    // three spaced-out point lights instead of one, still "basic lighting".
    for (const [fx, fz] of [[0.2, 0.3], [0.6, 0.4], [0.85, 0.7]]) {
      const light = new THREE.PointLight(0xfff2d8, 0.7, Math.max(bounds.width, bounds.depth) * 1.3, 1.7);
      light.position.set(bounds.minX + bounds.width * fx, 9.8, bounds.minZ + bounds.depth * fz);
      scene.add(light);
    }

    const gridHelper = new THREE.GridHelper(Math.max(bounds.width, bounds.depth) * 1.3, 30);
    gridHelper.position.set(bounds.centerX, -0.01, bounds.centerZ);
    scene.add(gridHelper);

    // Overview camera: pulled back and elevated so the whole unit is
    // visible on load (Requirement: verify all rooms appear in one scene).
    const overviewTarget = new THREE.Vector3(bounds.centerX, EYE_HEIGHT_FT, bounds.centerZ);
    const overviewDistance = Math.max(bounds.width, bounds.depth) * 1.1;
    camera.position.set(
      bounds.centerX - overviewDistance * 0.35,
      overviewDistance * 0.55,
      bounds.centerZ + overviewDistance * 0.7,
    );

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(overviewTarget);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1;
    controls.maxDistance = Math.max(bounds.width, bounds.depth) * 3;
    controls.update();

    // Smooth camera transition when navigating to a room (lerped over a
    // handful of frames rather than an instant jump), plus click-to-select.
    let flight = null; // { fromPos, toPos, fromTarget, toTarget, t }
    const FLIGHT_MS = 700;

    function highlightRoom(roomId) {
      for (const [id, p] of placed) {
        p.floorMat.color.set(id === roomId ? SELECTED_FLOOR_COLOR : 0xb9ada0);
      }
    }

    function selectRoom(roomId) {
      const p = placed.get(roomId);
      if (!p) return;
      highlightRoom(roomId);
      setSelectedId(roomId);

      const toTarget = new THREE.Vector3(p.centerX, EYE_HEIGHT_FT, p.centerZ);
      // Vantage point: just inside the room from its own "north" edge,
      // same convention as the single-room POC's entry camera.
      const inset = Math.min(4, p.depth / 2.2);
      const toPos = new THREE.Vector3(p.centerX, EYE_HEIGHT_FT, p.centerZ - p.depth / 2 + inset);

      flight = {
        fromPos: camera.position.clone(), toPos,
        fromTarget: controls.target.clone(), toTarget,
        start: performance.now(),
      };
    }
    apiRef.current = { selectRoom };

    // Click-to-select via raycasting, distinguishing a real click from an
    // OrbitControls drag (only select if the pointer barely moved and the
    // press was brief).
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let downX = 0, downY = 0, downT = 0;

    const onPointerDown = (e) => { downX = e.clientX; downY = e.clientY; downT = performance.now(); };
    const onPointerUp = (e) => {
      const moved = Math.hypot(e.clientX - downX, e.clientY - downY);
      const elapsed = performance.now() - downT;
      if (moved > CLICK_MAX_MOVE_PX || elapsed > CLICK_MAX_MS) return; // was a drag, not a click
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(selectableMeshes, false);
      if (hits.length > 0) {
        const roomId = hits[0].object.userData.roomId;
        if (roomId) selectRoom(roomId);
      }
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      if (flight) {
        const t = Math.min(1, (performance.now() - flight.start) / FLIGHT_MS);
        const ease = 1 - (1 - t) * (1 - t); // ease-out
        camera.position.lerpVectors(flight.fromPos, flight.toPos, ease);
        controls.target.lerpVectors(flight.fromTarget, flight.toTarget, ease);
        if (t >= 1) flight = null;
      }
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      cancelAnimationFrame(frameId);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  const roomIds = new Set(CONTINUUM_ROOMS.map((r) => r.room_id));

  return (
    <div style={styles.page}>
      <div style={styles.hud}>
        <div style={styles.title}>Continuum Residence 01 &middot; Whole Unit (Tower Residence 01)</div>
        <div style={styles.subtitle}>{CONTINUUM_ROOMS.length} rooms &middot; Three.js proof of concept</div>
        <div style={styles.hint}>Drag to orbit &middot; scroll to zoom &middot; right-drag to pan &middot; click a room (in 3D or the list) to select/navigate</div>
      </div>

      <div style={styles.roomList}>
        <div style={styles.roomListTitle}>Rooms</div>
        {CONTINUUM_ROOMS.map((r) => (
          <button
            key={r.room_id}
            style={{ ...styles.roomButton, ...(selectedId === r.room_id ? styles.roomButtonActive : {}) }}
            onClick={() => apiRef.current?.selectRoom(r.room_id)}
          >
            {r.name}
          </button>
        ))}
        {selectedId && (
          <div style={styles.linksBox}>
            <div style={styles.linksTitle}>Connects to</div>
            {CONTINUUM_ROOMS.find((r) => r.room_id === selectedId)?.links.map((to) => (
              <button
                key={to}
                disabled={!roomIds.has(to)}
                style={{ ...styles.linkButton, ...(roomIds.has(to) ? {} : styles.linkButtonDisabled) }}
                onClick={() => roomIds.has(to) && apiRef.current?.selectRoom(to)}
                title={roomIds.has(to) ? undefined : "No geometry for this room (excluded - see report)"}
              >
                {CONTINUUM_ROOMS.find((r) => r.room_id === to)?.name ?? to}
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={mountRef} style={styles.canvasHost} />
    </div>
  );
}

const styles = {
  page: {
    position: "fixed",
    inset: 0,
    background: "#111418",
    fontFamily: "Inter, Arial, sans-serif",
    color: "#fff",
  },
  canvasHost: {
    position: "absolute",
    inset: 0,
  },
  hud: {
    position: "absolute",
    top: 16,
    left: 16,
    zIndex: 2,
    background: "rgba(0,0,0,.55)",
    padding: "10px 14px",
    borderRadius: 8,
    pointerEvents: "none",
    maxWidth: 520,
  },
  title: { fontSize: 15, fontWeight: 600 },
  subtitle: { fontSize: 12, color: "#c7a45c", marginTop: 4 },
  hint: { fontSize: 11, color: "#9ca4a8", marginTop: 6 },
  roomList: {
    position: "absolute",
    top: 16,
    right: 16,
    zIndex: 2,
    background: "rgba(0,0,0,.65)",
    padding: 12,
    borderRadius: 8,
    width: 200,
    maxHeight: "calc(100vh - 32px)",
    overflowY: "auto",
  },
  roomListTitle: { fontSize: 12, color: "#9ca4a8", letterSpacing: 1, marginBottom: 8 },
  roomButton: {
    display: "block",
    width: "100%",
    textAlign: "left",
    background: "#1c2226",
    color: "#fff",
    border: "1px solid #333a3f",
    borderRadius: 5,
    padding: "8px 10px",
    marginBottom: 6,
    cursor: "pointer",
    fontSize: 13,
  },
  roomButtonActive: {
    background: "#b88a2b",
    border: "1px solid #d6b46a",
  },
  linksBox: { marginTop: 10, borderTop: "1px solid #333a3f", paddingTop: 10 },
  linksTitle: { fontSize: 11, color: "#9ca4a8", marginBottom: 6 },
  linkButton: {
    display: "block",
    width: "100%",
    textAlign: "left",
    background: "#151a1c",
    color: "#d6b46a",
    border: "1px solid #2a3034",
    borderRadius: 5,
    padding: "6px 9px",
    marginBottom: 5,
    cursor: "pointer",
    fontSize: 12,
  },
  linkButtonDisabled: {
    color: "#666",
    cursor: "not-allowed",
  },
};
