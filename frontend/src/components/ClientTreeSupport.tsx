"use client";

/**
 * AutoSlice — Client-side tree support layer for ModelViewer.
 *
 * Runs the full JavaScript tree support pipeline (overhang detection →
 * clustering → graph building → mesh generation) directly in the browser
 * using the already-loaded THREE.Object3D from the model viewer.
 *
 * Usage (inside a @react-three/fiber Canvas):
 *
 *   <ClientTreeSupportLayer object={loadedObject} config={{ overhangAngleDeg: 45 }} />
 */

import { useEffect, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { TreeSupportGenerator } from "@/lib/tree-support/TreeSupportGenerator";
import type { SupportConfig, SupportStats, TreeSupportResult } from "@/lib/tree-support/types";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ClientTreeSupportLayerProps {
  /** The loaded Three.js model object (from ThreeMFLoader). */
  object:      THREE.Object3D;
  /** Partial config — merged with DEFAULT_CONFIG. */
  config?:     Partial<SupportConfig>;
  /** Called after generation completes — receives full result. */
  onGenerated?: (result: TreeSupportResult) => void;
  /** Show debug node spheres in addition to support mesh. */
  showDebug?:  boolean;
  /** Opacity of the support mesh. */
  opacity?:    number;
}

// ── Inner Three.js component ───────────────────────────────────────────────────

/**
 * Must be rendered inside a @react-three/fiber Canvas.
 */
export function ClientTreeSupportLayer({
  object,
  config,
  onGenerated,
  showDebug = false,
  opacity   = 1.0,
}: ClientTreeSupportLayerProps) {
  const groupRef      = useRef<THREE.Group>(null);
  const debugGroupRef = useRef<THREE.Group>(null);
  const [generated, setGenerated] = useState(false);

  useEffect(() => {
    if (!object) return;
    setGenerated(false);

    // Run generation asynchronously so it does not block the render loop
    const id = requestAnimationFrame(() => {
      try {
        const gen    = new TreeSupportGenerator(config ?? {});
        const result = gen.generate(object, showDebug);

        // Apply opacity to all materials in the support mesh
        if (opacity < 0.99) {
          result.supportMesh.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const m = (child as THREE.Mesh).material as THREE.MeshStandardMaterial;
              m.transparent = true;
              m.opacity     = opacity;
              m.depthWrite  = false;
            }
          });
        }

        if (groupRef.current) {
          // Clear any previous support mesh
          while (groupRef.current.children.length > 0) {
            groupRef.current.remove(groupRef.current.children[0]);
          }
          groupRef.current.add(result.supportMesh);
        }

        if (showDebug && result.debugGroup && debugGroupRef.current) {
          while (debugGroupRef.current.children.length > 0) {
            debugGroupRef.current.remove(debugGroupRef.current.children[0]);
          }
          debugGroupRef.current.add(result.debugGroup);
        }

        console.log("[ClientTreeSupport] result", {
          segments: result.segments.length,
          nodes: result.nodes.size,
          meshChildren: result.supportMesh.children.length,
          stats: result.stats,
        });
        setGenerated(true);
        onGenerated?.(result);
      } catch (err) {
        console.error("[ClientTreeSupport] Generation failed:", err);
      }
    });

    return () => cancelAnimationFrame(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [object, JSON.stringify(config), showDebug, opacity]);

  // Dim the group during generation
  useFrame(() => {
    if (groupRef.current) {
      groupRef.current.visible = generated;
    }
  });

  return (
    <>
      <group ref={groupRef} name="client-tree-support" />
      {showDebug && <group ref={debugGroupRef} name="client-tree-support-debug" />}
    </>
  );
}

// ── Status badge (HTML overlay, outside Canvas) ────────────────────────────────

interface TreeSupportStatusProps {
  stats: SupportStats | null;
  generating: boolean;
}
export type { TreeSupportResult };

export function TreeSupportStatus({ stats, generating }: TreeSupportStatusProps) {
  if (generating) {
    return (
      <div className="absolute top-2 left-2 z-20 rounded-md bg-black/60 px-2 py-1 text-[11px] text-blue-300">
        Generating supports…
      </div>
    );
  }
  if (!stats) return null;

  const volCm3 = (stats.estimatedVolumeMm3 / 1000).toFixed(2);
  return (
    <div className="absolute top-2 left-2 z-20 rounded-md bg-black/60 px-2 py-1 text-[11px] text-zinc-300 space-y-0.5">
      <div className="font-semibold text-blue-300">Tree Supports (client)</div>
      <div>Trunks: <span className="text-white">{stats.trunkCount}</span></div>
      <div>Tips: <span className="text-white">{stats.tipCount}</span></div>
      <div>Clusters: <span className="text-white">{stats.clusterCount}</span></div>
      <div>Volume: <span className="text-white">{volCm3} cm³</span></div>
    </div>
  );
}
