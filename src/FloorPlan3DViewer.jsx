import React, { useRef, useEffect, useState } from "react";
import * as THREE from "three";

const ROOMS = [
  { name: "Bedroom 3", x: -18, z: -10, w: 12, d: 14, h: 9, color: "#e8ddc9" },
  { name: "Bedroom 2", x: -4, z: -12, w: 13, d: 14, h: 9, color: "#e3d6c0" },
  { name: "Living Room", x: 6, z: 2, w: 20, d: 18, h: 9, color: "#f2ede0" },
  { name: "Kitchen", x: -10, z: 6, w: 12, d: 11, h: 9, color: "#ded2ba" },
  { name: "Primary Bedroom", x: 26, z: -6, w: 16, d: 20, h: 9, color: "#e9dcc4" },
  { name: "Primary Bath", x: 26, z: 10, w: 10, d: 10, h: 9, color: "#cbd3d1" },
  { name: "Bath 2", x: -4, z: -3, w: 6, d: 7, h: 9, color: "#c9d1cf" },
  { name: "Bath 3", x: -18, z: 0, w: 6, d: 7, h: 9, color: "#c9d1cf" },
  { name: "Powder Room", x: 1, z: 12, w: 5, d: 5, h: 9, color: "#c9d1cf" },
];

const WALL_THICKNESS = 0.4;
const WALL_COLOR = "#a89a83";

function buildRoom(scene, room) {
  const { x, z, w, d, h, color, name } = room;

  const floorGeo = new THREE.PlaneGeometry(w, d);
  const floorMat = new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(x, 0, z);
  scene.add(floor);

  const wallMat = new THREE.MeshStandardMaterial({ color: WALL_COLOR });
  const wallsData = [
    { w: w + WALL_THICKNESS, d: WALL_THICKNESS, x: x, z: z - d / 2 },
    { w: w + WALL_THICKNESS, d: WALL_THICKNESS, x: x, z: z + d / 2 },
    { w: WALL_THICKNESS, d: d, x: x - w / 2, z: z },
    { w: WALL_THICKNESS, d: d, x: x + w / 2, z: z },
  ];
  wallsData.forEach((wd) => {
    const geo = new THREE.BoxGeometry(wd.w, h, wd.d);
    const mesh = new THREE.Mesh(geo, wallMat);
    mesh.position.set(wd.x, h / 2, wd.z);
    scene.add(mesh);
  });

  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "rgba(30,26,20,0.85)";
  ctx.fillRect(0, 0, 256, 64);
  ctx.fillStyle = "#f2ede0";
  ctx.font = "28px Georgia";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(name, 128, 32);
  const texture = new THREE.CanvasTexture(canvas);
  const spriteMat = new THREE.SpriteMaterial({ map: texture, depthTest: false });
  const sprite = new THREE.Sprite(spriteMat);
  sprite.scale.set(6, 1.5, 1);
  sprite.position.set(x, h + 2, z);
  scene.add(sprite);
}

export default function FloorPlan3DViewer() {
  const mountRef = useRef(null);
  const [hint, setHint] = useState(true);

  useEffect(() => {
    const mount = mountRef.current;
    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#dfe6e8");

    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 500);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const sun = new THREE.DirectionalLight(0xffffff, 0.8);
    sun.position.set(40, 60, 20);
    scene.add(sun);

    const groundGeo = new THREE.PlaneGeometry(200, 200);
    const groundMat = new THREE.MeshStandardMaterial({ color: "#c7cfce" });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.05;
    scene.add(ground);

    ROOMS.forEach((r) => buildRoom(scene, r));

    let radius = 70;
    let theta = Math.PI / 4;
    let phi = Math.PI / 3.2;
    const target = new THREE.Vector3(4, 0, 0);

    function updateCamera() {
      const x = target.x + radius * Math.sin(phi) * Math.sin(theta);
      const y = target.y + radius * Math.cos(phi);
      const z = target.z + radius * Math.sin(phi) * Math.cos(theta);
      camera.position.set(x, y, z);
      camera.lookAt(target);
    }
    updateCamera();

    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const onPointerDown = (e) => {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      setHint(false);
    };
    const onPointerUp = () => {
      dragging = false;
    };
    const onPointerMove = (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      theta -= dx * 0.006;
      phi -= dy * 0.006;
      phi = Math.max(0.2, Math.min(Math.PI / 2 - 0.05, phi));
      updateCamera();
    };
    const onWheel = (e) => {
      e.preventDefault();
      radius += e.deltaY * 0.05;
      radius = Math.max(15, Math.min(150, radius));
      updateCamera();
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("wheel", onWheel, { passive: false });

    let frameId;
    const animate = () => {
      frameId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("wheel", onWheel);
      mount.removeChild(renderer.domElement);
      renderer.dispose();
    };
  }, []);

  return (
    <div style={{ width: "100%", height: "100%", background: "#f7f5f0", fontFamily: "Georgia, serif" }}>
      <div style={{ padding: "14px 18px", borderBottom: "1px solid #ddd6c9" }}>
        <div style={{ fontSize: 20, color: "#2c2620" }}>Tower Residence 01 — 3D Prototype</div>
        <div style={{ fontSize: 13, color: "#7a7263", marginTop: 2 }}>
          Continuum Club &amp; Residences · Floors 7–23 · 3 bed / 3.5 bath
        </div>
      </div>
      <div style={{ position: "relative", width: "100%", height: "calc(100% - 58px)" }}>
        <div ref={mountRef} style={{ width: "100%", height: "100%" }} />
        {hint && (
          <div
            style={{
              position: "absolute",
              bottom: 14,
              left: 14,
              background: "rgba(44,38,32,0.75)",
              color: "#f2ede0",
              padding: "8px 12px",
              borderRadius: 4,
              fontSize: 13,
            }}
          >
            Drag to orbit · Scroll to zoom
          </div>
        )}
      </div>
    </div>
  );
}