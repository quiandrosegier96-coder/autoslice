"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { processModel }         from "@/lib/processModel";
import { detectOverhangFaces } from "@/lib/detectOverhangFaces";
import { generateTreeSupports }         from "@/lib/generateTreeSupports";
import { exportSTL }                    from "@/lib/exportSTL";

// ── Materials ──────────────────────────────────────────────────────────────────

const MODEL_MATERIAL = new THREE.MeshStandardMaterial({
  color:     0xcc2222,
  roughness: 0.6,
  metalness: 0.1,
});

const SUPPORT_MATERIAL = new THREE.MeshStandardMaterial({
  color:       0x888888,
  transparent: true,
  opacity:     0.65,
  depthWrite:  false,
});

// ── Component ──────────────────────────────────────────────────────────────────

export function StandaloneModelViewer() {
  const mountRef    = useRef<HTMLDivElement>(null);
  const sceneRef    = useRef<THREE.Scene | null>(null);
  const cameraRef   = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rafRef      = useRef<number | null>(null);

  const [model,    setModel]    = useState<THREE.Mesh | null>(null);
  const [supports, setSupports] = useState<THREE.Group | null>(null);
  const [status,   setStatus]   = useState<string>("Upload a model to begin.");
  const [loading,  setLoading]  = useState(false);

  // ── Scene setup ──────────────────────────────────────────────────────────────

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x141414);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(
      45,
      mount.clientWidth / mount.clientHeight,
      0.1,
      5000,
    );
    camera.position.set(0, 100, 200);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controlsRef.current = controls;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.5));
    const sun = new THREE.DirectionalLight(0xffffff, 1.5);
    sun.position.set(80, 150, 80);
    sun.castShadow = true;
    scene.add(sun);
    scene.add(new THREE.DirectionalLight(0xffffff, 0.3).position.set(-80, -50, -80) && sun);
    const fill = new THREE.DirectionalLight(0xffffff, 0.3);
    fill.position.set(-80, -50, -80);
    scene.add(fill);

    // Grid
    const grid = new THREE.GridHelper(400, 40, 0x333333, 0x222222);
    scene.add(grid);

    // Render loop
    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize
    const onResize = () => {
      if (!mount) return;
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, []);

  // ── Scene helpers ────────────────────────────────────────────────────────────

  const removeFromScene = useCallback((obj: THREE.Object3D | null) => {
    if (!obj || !sceneRef.current) return;
    sceneRef.current.remove(obj);
    obj.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.geometry?.dispose();
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((m) => m.dispose());
        } else {
          mesh.material?.dispose();
        }
      }
    });
  }, []);

  const fitCamera = useCallback((mesh: THREE.Mesh) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    const box    = new THREE.Box3().setFromObject(mesh);
    const size   = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    camera.position.set(
      center.x + maxDim * 1.2,
      center.y + maxDim * 0.8,
      center.z + maxDim * 1.5,
    );
    camera.lookAt(center);
    controls.target.copy(center);
    controls.update();
  }, []);

  // ── File upload ───────────────────────────────────────────────────────────────

  const handleFile = useCallback(async (file: File) => {
    const scene = sceneRef.current;
    if (!scene) return;

    setLoading(true);
    setStatus("Loading model…");

    // Clear previous
    removeFromScene(model);
    removeFromScene(supports);
    setModel(null);
    setSupports(null);

    try {
      const url = URL.createObjectURL(file);
      const ext = file.name.split(".").pop()?.toLowerCase();

      let root: THREE.Object3D;

      if (ext === "stl") {
        const loader   = new STLLoader();
        const geometry = await new Promise<THREE.BufferGeometry>((res, rej) =>
          loader.load(url, res, undefined, rej),
        );
        root = new THREE.Mesh(geometry, MODEL_MATERIAL.clone());
      } else {
        const loader = new GLTFLoader();
        const gltf   = await new Promise<{ scene: THREE.Group }>((res, rej) =>
          loader.load(url, res as never, undefined, rej),
        );
        root = gltf.scene;
      }

      URL.revokeObjectURL(url);

      const { mesh, supports: initialSupports } = processModel(root);
      scene.add(mesh);

      setModel(mesh);
      setSupports(initialSupports);
      fitCamera(mesh);
      setStatus(`Model loaded. ${mesh.geometry.index?.count ?? 0} indices.`);
    } catch (err) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }, [model, supports, removeFromScene, fitCamera]);

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      e.target.value = "";
    },
    [handleFile],
  );

  // ── Generate supports ─────────────────────────────────────────────────────────

  const handleGenerateSupports = useCallback(() => {
    const scene = sceneRef.current;
    if (!model || !scene) return;

    removeFromScene(supports);
    setSupports(null);
    setStatus("Detecting overhangs…");

    const faces = detectOverhangFaces(model.geometry, 50);
    if (!faces.length) {
      setStatus("No overhangs detected.");
      return;
    }

    const group = generateTreeSupports(faces, model, { material: SUPPORT_MATERIAL.clone() });
    scene.add(group);
    setSupports(group);
    setStatus(`Generated ${group.children.length} support pillars from ${faces.length} overhang faces.`);
  }, [model, supports, removeFromScene]);

  // ── Export ────────────────────────────────────────────────────────────────────

  const handleExport = useCallback(() => {
    if (!model) return;
    setStatus("Exporting STL…");
    try {
      exportSTL(model, supports, {
        modelFilename:    "model.stl",
        supportsFilename: "supports.stl",
      });
      setStatus("Export complete.");
    } catch (err) {
      setStatus(`Export error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [model, supports]);

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full w-full bg-[#0e0e0e]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 shrink-0">
        <label className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium bg-white/10 hover:bg-white/15 text-zinc-200 transition-colors">
          Upload Model
          <input
            type="file"
            accept=".glb,.gltf,.stl"
            className="hidden"
            onChange={onInputChange}
          />
        </label>

        <button
          onClick={handleGenerateSupports}
          disabled={!model || loading}
          className="rounded-lg px-3 py-1.5 text-sm font-medium bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          Generate Supports
        </button>

        <button
          onClick={handleExport}
          disabled={!model || loading}
          className="rounded-lg px-3 py-1.5 text-sm font-medium bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 disabled:cursor-not-allowed text-white transition-colors"
        >
          Export STL
        </button>

        <span className="ml-auto text-xs text-zinc-500 truncate max-w-xs">
          {loading ? "Processing…" : status}
        </span>
      </div>

      {/* Viewport */}
      <div ref={mountRef} className="flex-1 w-full" />
    </div>
  );
}
