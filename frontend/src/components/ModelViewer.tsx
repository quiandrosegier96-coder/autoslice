"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { ThreeMFLoader } from "three/examples/jsm/loaders/3MFLoader.js";
import * as THREE from "three";
import { SupportVisualization, SupportDebugLayerToggles } from "./SupportVisualization";
import { processModel }          from "@/lib/processModel";
import { detectOverhangFaces }   from "@/lib/detectOverhangFaces";
import { generateTreeSupports }       from "@/lib/generateTreeSupports";
import type { TreeSupportOptions }    from "@/lib/generateTreeSupports";
import { exportSTL }             from "@/lib/exportSTL";
import {
  generateLayerPreview,
  disposeLayerPreview,
} from "@/lib/generateLayerPreview";
import type { LayerPreviewResult } from "@/lib/generateLayerPreview";
import { ClientTreeSupportLayer, TreeSupportStatus } from "./ClientTreeSupport";
import { SupportGrowthAnimation } from "./viewer/SupportGrowthAnimation";
import { DebugGraphOverlay }      from "./viewer/DebugGraphOverlay";
import { DebugFaceOverlay }       from "./viewer/DebugFaceOverlay";
import { BedPlate }               from "./viewer/BedPlate";
import type { BedPlateType }           from "./viewer/BedPlate";
import type { SupportConfig, SupportStats, TreeSupportResult } from "@/lib/tree-support/types";
import type { ExtendedViewMode }       from "./viewer/TreeSupportPanel";

// ── AutoCamera ────────────────────────────────────────────────────────────────

function AutoCamera({ object }: { object: THREE.Group }) {
  const { camera } = useThree();
  useEffect(() => {
    const box    = new THREE.Box3().setFromObject(object);
    const size   = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);
    // Centre X/Z; align bottom to Y = 0 so model always sits on the build plate
    object.position.x -= (box.min.x + box.max.x) / 2;
    object.position.z -= (box.min.z + box.max.z) / 2;
    object.position.y -= box.min.y;          // lift so min.y = 0
    const modelCenterY = size.y / 2;
    const cam = camera as THREE.PerspectiveCamera;
    const fov = cam.fov * (Math.PI / 180);
    const dist = (maxDim / 2) / Math.tan(fov / 2) * 1.8;
    camera.position.set(dist * 0.6, modelCenterY + dist * 0.45, dist);
    camera.lookAt(0, modelCenterY, 0);
    cam.near = dist * 0.001;
    cam.far  = dist * 10;
    cam.updateProjectionMatrix();
  }, [object, camera]);
  return null;
}

// ── CameraReset ───────────────────────────────────────────────────────────────

function CameraReset({ resetKey }: { resetKey: number }) {
  const { camera, controls } = useThree();
  useEffect(() => {
    if (!resetKey) return;
    camera.position.set(0, 0, 200);
    camera.lookAt(0, 0, 0);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (controls as any)?.reset?.();
  }, [resetKey, camera, controls]);
  return null;
}

// BuildPlateGrid is replaced by the BedPlate component from ./viewer/BedPlate.

// ── Model ─────────────────────────────────────────────────────────────────────

function Model({
  url,
  wireframe = false,
  opacity   = 1,
  onObjectLoaded,
}: {
  url:             string;
  wireframe?:      boolean;
  opacity?:        number;
  onObjectLoaded?: (object: THREE.Group) => void;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const object = useLoader(ThreeMFLoader as any, url) as THREE.Group;

  useEffect(() => {
    const transparent = opacity < 0.99;
    object.traverse(child => {
      if ((child as THREE.Mesh).isMesh) {
        const mesh = child as THREE.Mesh;
        mesh.material = new THREE.MeshStandardMaterial({
          color:      wireframe ? "#888888" : "#cc2222",
          wireframe,
          roughness:  0.6,
          metalness:  0.1,
          transparent,
          opacity,
          depthWrite: !transparent,
        });
        mesh.visible = opacity > 0.01;
      }
    });
    onObjectLoaded?.(object);
  }, [object, wireframe, opacity, onObjectLoaded]);

  return (
    <>
      <primitive object={object} />
      <AutoCamera object={object} />
    </>
  );
}

// ── Static support mesh ───────────────────────────────────────────────────────

function StaticSupportMesh({
  result,
  opacity = 1,
}: {
  result:   TreeSupportResult;
  opacity?: number;
}) {
  useEffect(() => {
    result.supportMesh.traverse(child => {
      if ((child as THREE.Mesh).isMesh) {
        const m = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
        m.transparent = opacity < 0.99;
        m.opacity     = opacity;
        m.depthWrite  = opacity >= 0.99;
        m.needsUpdate = true;
      }
    });
  }, [result, opacity]);
  return <primitive object={result.supportMesh} />;
}

// ── Loading fallback ──────────────────────────────────────────────────────────

function LoadingBox() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#333" wireframe />
    </mesh>
  );
}

// ── Layer preview renderer ────────────────────────────────────────────────────

function LayerPreview({
  result,
  selectedLayer,
  mode,
}: {
  result:        LayerPreviewResult;
  selectedLayer: number;
  mode:          "current" | "cumulative";
}) {
  const idx    = Math.max(0, Math.min(selectedLayer, result.layerCount - 1));
  const layers = mode === "current"
    ? (result.layers[idx] ? [result.layers[idx]] : [])
    : result.layers.slice(0, idx + 1);

  return (
    <>
      {layers.map(layer => (
        <group key={layer.index}>
          {layer.modelSegments && (
            <lineSegments geometry={layer.modelSegments}>
              <lineBasicMaterial color="#e05555" />
            </lineSegments>
          )}
          {layer.supportsSegments && (
            <lineSegments geometry={layer.supportsSegments}>
              <lineBasicMaterial color="#aaaaaa" />
            </lineSegments>
          )}
        </group>
      ))}
    </>
  );
}

// ── Props ─────────────────────────────────────────────────────────────────────

export type { BedPlateType };

interface ModelViewerProps {
  jobId:         string;
  // Legacy mode support (maps to ExtendedViewMode)
  showSupports?: boolean;
  wireframe?:    boolean;
  modelOpacity?: number;
  heatmapOnly?:  boolean;
  // Extended mode
  viewMode?:     ExtendedViewMode;
  // Bed plate
  bedPlateType?: BedPlateType;
  // Client-side tree support
  showClientTreeSupport?:    boolean;
  clientSupportConfig?:      Partial<SupportConfig>;
  onClientSupportGenerated?: (result: TreeSupportResult) => void;
  // Animation controls (passed in from parent)
  treeResult?:       TreeSupportResult | null;
  animPlaying?:      boolean;
  animProgress?:     number;
  animSpeed?:        number;
  onAnimProgress?:   (p: number) => void;
  selectedSegmentId?: number | null;
  selectedNodeId?:    number | null;
  onSegmentClick?:    (id: number | null) => void;
  onNodeClick?:       (id: number | null) => void;
  // Legacy debug
  className?:    string;
  resetKey?:     number;
  debugMode?:    boolean;
  debugLayers?:  SupportDebugLayerToggles;
  // Pipeline callbacks — optional, does not affect existing behavior
  onPipelineReady?: (handlers: {
    generateSupports: () => void;
    exportSTL:        () => void;
  }) => void;
  treeSupportOptions?: TreeSupportOptions;
  // Layer preview
  previewEnabled?: boolean;
  previewMode?:    "current" | "cumulative";
  selectedLayer?:  number;
  layerHeight?:    number;
  onLayerPreviewReady?: (info: { layerCount: number; minY: number; maxY: number }) => void;
}

// ── Main exported component ───────────────────────────────────────────────────

export function ModelViewer({
  jobId,
  showSupports = false,
  wireframe    = false,
  modelOpacity = 1,
  heatmapOnly  = false,
  viewMode,
  bedPlateType = "smooth_pei",
  showClientTreeSupport    = false,
  clientSupportConfig,
  onClientSupportGenerated,
  treeResult,
  animPlaying  = false,
  animProgress = 0,
  animSpeed    = 1,
  onAnimProgress,
  selectedSegmentId = null,
  selectedNodeId    = null,
  onSegmentClick,
  onNodeClick,
  className    = "w-full h-72 bg-surface-card rounded-xl overflow-hidden border border-surface-border relative",
  resetKey,
  debugMode    = false,
  debugLayers,
  onPipelineReady,
  treeSupportOptions,
  previewEnabled = false,
  previewMode    = "current",
  selectedLayer  = 0,
  layerHeight    = 0.2,
  onLayerPreviewReady,
}: ModelViewerProps) {
  const url = `/api/upload/${jobId}/file`;

  // Resolve effective mode from either viewMode prop or legacy props
  const effectiveMode: ExtendedViewMode = viewMode ?? (
    heatmapOnly     ? "heatmap" :
    !showSupports   ? "model"   :
    modelOpacity < 0.1 ? "supports" :
    modelOpacity < 0.5 ? "transparent+supports" :
    "model+supports"
  );

  // Derive per-mode display settings
  const effectiveModelOpacity =
    effectiveMode === "supports"             ? 0.0  :
    effectiveMode === "transparent+supports" ? 0.18 :
    modelOpacity;

  const showHeatmap  = effectiveMode === "heatmap" || effectiveMode === "heatmap+supports";
  const showSupportM = effectiveMode !== "model" && effectiveMode !== "heatmap" && effectiveMode !== "debug-graph";
  const showDebugGraph = effectiveMode === "debug-graph";
  const showAnimation  = (animPlaying || animProgress > 0) && treeResult != null;

  const [loadedObject,     setLoadedObject]     = useState<THREE.Group | null>(null);
  const [clientStats,      setClientStats]      = useState<SupportStats | null>(null);
  const [generating,       setGenerating]       = useState(false);
  const [pipelineMesh,     setPipelineMesh]     = useState<THREE.Mesh | null>(null);
  const [pipelineSupports, setPipelineSupports] = useState<THREE.Group | null>(null);
  const [layerPreview,     setLayerPreview]     = useState<LayerPreviewResult | null>(null);

  // Generate layer preview whenever inputs or settings change
  useEffect(() => {
    if (!previewEnabled || !pipelineMesh) {
      setLayerPreview(null);
      return;
    }
    const id = setTimeout(() => {
      setLayerPreview(prev => {
        if (prev) disposeLayerPreview(prev);
        const result = generateLayerPreview(
          pipelineMesh,
          pipelineSupports ?? undefined,
          { layerHeight },
        );
        onLayerPreviewReady?.({ layerCount: result.layerCount, minY: result.minY, maxY: result.maxY });
        return result;
      });
    }, 0);
    return () => clearTimeout(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewEnabled, pipelineMesh, pipelineSupports, layerHeight, onLayerPreviewReady]);

  // Dispose geometries when preview is replaced or component unmounts
  useEffect(() => () => { if (layerPreview) disposeLayerPreview(layerPreview); }, [layerPreview]);

  function handleObjectLoaded(obj: THREE.Group) {
    setLoadedObject(obj);
    if (showClientTreeSupport) setGenerating(true);
    // Run pipeline off the render thread; result used for supports + export
    setTimeout(() => {
      const { mesh } = processModel(obj);
      setPipelineMesh(mesh);
      setPipelineSupports(null);
    }, 0);
  }

  function handleGenerateSupports() {
    if (!pipelineMesh) return;
    const faces = detectOverhangFaces(pipelineMesh.geometry, 50);
    const group = generateTreeSupports(faces, pipelineMesh, treeSupportOptions);
    setPipelineSupports(group);
  }

  function handleExportSTL() {
    if (!pipelineMesh) return;
    exportSTL(pipelineMesh, pipelineSupports, {
      modelFilename:    "model.stl",
      supportsFilename: "supports.stl",
    });
  }

  // Expose handlers to parent via callback (does not affect existing behavior)
  useEffect(() => {
    onPipelineReady?.({
      generateSupports: handleGenerateSupports,
      exportSTL:        handleExportSTL,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelineMesh, pipelineSupports, onPipelineReady]);

  function handleClientGenerated(result: TreeSupportResult) {
    setClientStats(result.stats);
    setGenerating(false);
    onClientSupportGenerated?.(result);
  }

  // Build plate is always at Y = 0 (AutoCamera lifts the model to sit on it)
  const plateY = 0;

  return (
    <div className={className}>
      {showClientTreeSupport && (
        <TreeSupportStatus stats={clientStats} generating={generating} />
      )}

      <Canvas
        key={resetKey}
        camera={{ position: [0, 0, 200], fov: 45 }}
        gl={{ antialias: true }}
        shadows
      >
        <color attach="background" args={["#141414"]} />

        {/* Lighting */}
        <ambientLight intensity={0.45} />
        <directionalLight position={[10, 20, 10]}  intensity={1.5} castShadow
          shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
        <directionalLight position={[-8, -5, -8]}  intensity={0.25} />
        <directionalLight position={[0,  -15, 5]}  intensity={0.15} />

        {/* Build plate — visually distinct per bed type */}
        <BedPlate plateY={plateY} bedType={bedPlateType} />

        {/* Camera reset helper */}
        {resetKey !== undefined && <CameraReset resetKey={resetKey} />}

        <Suspense fallback={<LoadingBox />}>
          {/* Model */}
          <Model
            url={url}
            wireframe={wireframe}
            opacity={effectiveModelOpacity}
            onObjectLoaded={handleObjectLoaded}
          />

          {/* Backend support visualization (heatmap + backend tree branches) */}
          {(showHeatmap || (showSupportM && !treeResult && !showClientTreeSupport)) && (
            <SupportVisualization
              jobId={jobId}
              debugMode={debugMode}
              debugLayers={debugLayers}
              heatmapOnly={showHeatmap && !showSupportM}
            />
          )}

          {/* Client-side tree generator (runs once, builds result) */}
          {showClientTreeSupport && loadedObject && (
            <ClientTreeSupportLayer
              object={loadedObject}
              config={clientSupportConfig}
              onGenerated={handleClientGenerated}
              showDebug={debugMode}
            />
          )}

          {/* Static support mesh (when not animating) */}
          {treeResult && showSupportM && !showAnimation && (
            <StaticSupportMesh
              result={treeResult}
              opacity={effectiveMode === "transparent+supports" ? 0.85 : 1}
            />
          )}

          {/* Growth animation */}
          {treeResult && showAnimation && (
            <SupportGrowthAnimation
              result={treeResult}
              playing={animPlaying}
              progress={animProgress}
              speed={animSpeed}
              onProgressUpdate={onAnimProgress ?? (() => {})}
              selectedSegmentId={selectedSegmentId}
              onSegmentClick={onSegmentClick ?? (() => {})}
            />
          )}

          {/* Debug graph overlay */}
          {treeResult && showDebugGraph && (
            <DebugGraphOverlay
              result={treeResult}
              selectedSegmentId={selectedSegmentId}
              selectedNodeId={selectedNodeId}
              onSegmentClick={onSegmentClick ?? (() => {})}
              onNodeClick={onNodeClick ?? (() => {})}
            />
          )}

          {/* Debug face overlay — coloured face layers (red/orange/yellow/green) */}
          {treeResult && showDebugGraph && (
            <DebugFaceOverlay result={treeResult} />
          )}

          {/* Pipeline supports — hidden when layer preview is active */}
          {pipelineSupports && !previewEnabled && (
            <primitive object={pipelineSupports} />
          )}

          {/* Layer preview — replaces solid supports when active */}
          {previewEnabled && layerPreview && (
            <LayerPreview
              result={layerPreview}
              selectedLayer={selectedLayer}
              mode={previewMode}
            />
          )}
        </Suspense>

        <OrbitControls makeDefault enableZoom enablePan enableRotate />
      </Canvas>
    </div>
  );
}
