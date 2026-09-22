import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { CONTINUUM_PRIMARY_ROOM } from "./data/continuumPrimaryRoomGeometry.js";
import { buildRoomGroup, createRoomMaterials } from "./roomBuilder.js";

const EYE_HEIGHT_FT = 5.5;
const ENTRY_INSET_FT = 5; // how far inside the room, from the entry wall, the camera starts

function buildRoom(room) {
  return buildRoomGroup(room, createRoomMaterials(), room.room_id);
}

export default function PrimaryRoomPOC() {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    const room = CONTINUUM_PRIMARY_ROOM;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111418);

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / mount.clientHeight,
      0.1,
      500,
    );

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const { group, width, depth, height } = buildRoom(room);
    scene.add(group);

    // Lighting: a soft sky/ground fill (Hemisphere), a directional "sun"
    // through the window direction, a flat AmbientLight so no face is ever
    // fully unlit, and an interior PointLight near the ceiling (like a room
    // fixture) specifically so the ceiling's underside and the corners
    // opposite the window are actually visible instead of reading as black.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x555045, 1.0));
    scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const sun = new THREE.DirectionalLight(0xfff4e0, 0.9);
    sun.position.set(width + 10, height + 10, depth * 0.5);
    scene.add(sun);
    const roomLight = new THREE.PointLight(0xfff2d8, 0.9, Math.max(width, depth) * 2.2, 1.6);
    roomLight.position.set(width / 2, height - 1.2, depth / 2);
    scene.add(roomLight);

    const gridHelper = new THREE.GridHelper(Math.max(width, depth) * 1.5, 20);
    gridHelper.position.set(width / 2, -0.01, depth / 2);
    scene.add(gridHelper);

    // Entry wall is wall_north (y = 0 side) - start the camera just inside
    // the room from there, at eye height.
    camera.position.set(width / 2, EYE_HEIGHT_FT, Math.min(ENTRY_INSET_FT, depth / 2));

    const controls = new OrbitControls(camera, renderer.domElement);
    // The orbit pivot must be a point INSIDE the open room volume, not on a
    // wall surface (an earlier version pointed it at the far wall itself,
    // which made small drags swing the camera wildly since it was orbiting
    // around a point right on the geometry). OrbitControls.update() always
    // re-aims the camera at this target - any camera.lookAt() called before
    // constructing OrbitControls would be overwritten by that anyway, so
    // this target is the only look-at that actually matters.
    controls.target.set(width / 2, EYE_HEIGHT_FT, depth / 2);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 1;
    controls.maxDistance = Math.max(width, depth) * 4;
    controls.update();

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
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
      cancelAnimationFrame(frameId);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  const room = CONTINUUM_PRIMARY_ROOM;

  return (
    <div style={styles.page}>
      <div style={styles.hud}>
        <div style={styles.title}>Continuum Residence 01 &middot; {room.name}</div>
        <div style={styles.subtitle}>
          {room.width_ft.toFixed(2)}&prime; &times; {room.depth_ft.toFixed(2)}&prime; &middot;{" "}
          {room.ceiling_ft.toFixed(0)}&prime; ceiling &middot; Three.js proof of concept
        </div>
        <div style={styles.hint}>Drag to orbit &middot; scroll to zoom &middot; right-drag to pan</div>
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
  },
  title: {
    fontSize: 15,
    fontWeight: 600,
  },
  subtitle: {
    fontSize: 12,
    color: "#c7a45c",
    marginTop: 4,
  },
  hint: {
    fontSize: 11,
    color: "#9ca4a8",
    marginTop: 6,
  },
};
