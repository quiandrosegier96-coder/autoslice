"use client";

import { Suspense, useEffect } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { ThreeMFLoader } from "three/examples/jsm/loaders/3MFLoader.js";
import * as THREE from "three";
import { SupportVisualization, SupportDebugLayerToggles } from "./SupportVisualization";

function AutoCamera({ object }: { object: THREE.Group }) {
  const { camera } = useThree();
  useEffect(() => {
    const box = new THREE.Box3().setFromObject(object);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    object.position.sub(center);
    const cam = camera as THREE.PerspectiveCamera;
    const fov = cam.fov * (Math.PI / 180);
    const dist = (maxDim / 2) / Math.tan(fov / 2) * 1.8;
    camera.position.set(dist * 0.6, dist * 0.45, dist);
    camera.lookAt(0, 0, 0);
    cam.near = dist * 0.001;
    cam.far = dist * 10;
    cam.updateProjectionMatrix();
  }, [object, camera]);
  return null;
}

function Model({ url, wireframe = false }: { url: string; wireframe?: boolean }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const object = useLoader(ThreeMFLoader as any, url) as THREE.Group;

  // Apply a clean material so the model is always visible
  useEffect(() => {
    object.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = new THREE.MeshStandardMaterial({
          color: wireframe ? "#888888" : "#cc2222",
          wireframe,
          roughness: 0.6,
          metalness: 0.1,
        });
      }
    });
  }, [object, wireframe]);

  return (
    <>
      <primitive object={object} />
      <AutoCamera object={object} />
    </>
  );
}

function LoadingBox() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#333" wireframe />
    </mesh>
  );
}

interface ModelViewerProps {
  jobId:         string;
  showSupports?: boolean;
  wireframe?:    boolean;
  /** Override the wrapper div className. Default includes h-72 and card styling. */
  className?:    string;
  /** Increment to remount the Canvas and reset camera to initial position. */
  resetKey?:     number;
  /** Pass true to fetch support-preview with ?debug=true */
  debugMode?:    boolean;
  /** Which debug layers to show (only used when debugMode=true) */
  debugLayers?:  SupportDebugLayerToggles;
}

export function ModelViewer({
  jobId,
  showSupports = false,
  wireframe    = false,
  className    = "w-full h-72 bg-surface-card rounded-xl overflow-hidden border border-surface-border relative",
  resetKey,
  debugMode    = false,
  debugLayers,
}: ModelViewerProps) {
  const url = `/api/upload/${jobId}/file`;
  return (
    <div className={className}>
      <p className="absolute bottom-2 right-3 text-[10px] text-zinc-600 pointer-events-none select-none z-10">
        drag to rotate · scroll to zoom
      </p>
      <Canvas key={resetKey} camera={{ position: [0, 0, 200], fov: 45 }} gl={{ antialias: true }}>
        <color attach="background" args={["#191919"]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 15, 10]} intensity={1.4} />
        <directionalLight position={[-8, -5, -8]} intensity={0.3} />
        <Suspense fallback={<LoadingBox />}>
          <Model url={url} wireframe={wireframe} />
          {showSupports && (
            <SupportVisualization
              jobId={jobId}
              debugMode={debugMode}
              debugLayers={debugLayers}
            />
          )}
        </Suspense>
        <OrbitControls enableZoom enablePan enableRotate />
      </Canvas>
    </div>
  );
}
