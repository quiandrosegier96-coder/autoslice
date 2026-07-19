"use client";

import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { buildBox } from "./BoxBuilder";
import { buildLid } from "./LidBuilder";
import {
  DEFAULT_SETTINGS,
  NOZZLES,
  PRESETS,
  TOLERANCES,
  WALL_PRESETS,
  BoxSettings,
  effectiveHingeClearance,
  pinDiameter,
} from "./Presets";
import { autoCorrect, validateSettings } from "./Validation";
import { cloneMeshesToGroup } from "./GeometryUtils";
import { exportStl, exportThreeMf, exportZip } from "./Exporter";

type HistoryState = {
  past: BoxSettings[];
  present: BoxSettings;
  future: BoxSettings[];
};

function alignToPlate(object: THREE.Object3D) {
  object.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object);
  object.position.y -= box.min.y;
}

function Preview({ box, lid, spacing }: { box: THREE.Group; lid: THREE.Group; spacing: number }) {
  const preview = useMemo(() => {
    const group = new THREE.Group();
    const boxClone = box.clone(true);
    const lidClone = lid.clone(true);
    boxClone.position.x = -spacing / 2;
    lidClone.position.x = spacing / 2;
    alignToPlate(boxClone);
    alignToPlate(lidClone);
    group.add(boxClone, lidClone);
    return group;
  }, [box, lid, spacing]);

  return <primitive object={preview} />;
}

function PreviewCamera({ spacing, plateSize, maxPartHeight }: { spacing: number; plateSize: number; maxPartHeight: number }) {
  const { camera, controls } = useThree();

  useMemo(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const target = new THREE.Vector3(0, maxPartHeight * 0.35, 0);
    const distance = Math.max(spacing * 0.95, plateSize * 1.25, 260);
    cam.position.set(0, distance * 0.62, distance * 0.86);
    cam.lookAt(target);
    cam.near = 0.1;
    cam.far = distance * 5;
    cam.fov = 38;
    cam.updateProjectionMatrix();
    const orbit = controls as { target?: THREE.Vector3; update?: () => void } | undefined;
    orbit?.target?.copy(target);
    orbit?.update?.();
  }, [camera, controls, spacing, plateSize, maxPartHeight]);

  return null;
}

function Plate({ x, label, size }: { x: number; label: string; size: number }) {
  return (
    <group position={[x, 0, 0]}>
      <gridHelper args={[size, Math.max(12, Math.round(size / 10)), "#1d2550", "#141a36"]} position={[0, -0.05, 0]} />
      <mesh position={[0, -0.08, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[size, size]} />
        <meshStandardMaterial color="#080a12" transparent opacity={0.34} />
      </mesh>
      <sprite position={[-size * 0.38, 0.5, -size * 0.43]} scale={[28, 8, 1]}>
        <spriteMaterial map={makeLabelTexture(label)} transparent />
      </sprite>
    </group>
  );
}

const labelTextureCache = new Map<string, THREE.CanvasTexture>();

function makeLabelTexture(label: string) {
  const cached = labelTextureCache.get(label);
  if (cached) return cached;
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "rgba(10,12,20,0.86)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "rgba(255,255,255,0.16)";
    ctx.strokeRect(2, 2, canvas.width - 4, canvas.height - 4);
    ctx.fillStyle = "#e4e4e7";
    ctx.font = "700 42px Arial";
    ctx.fillText(label, 34, 78);
  }
  const texture = new THREE.CanvasTexture(canvas);
  labelTextureCache.set(label, texture);
  return texture;
}

function Field({
  label,
  value,
  min,
  max,
  step = 0.1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-500">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-10 w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 text-sm font-semibold text-zinc-100 outline-none transition focus:border-brand/70 focus:bg-white/[0.06]"
      />
    </label>
  );
}

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
        className="h-10 w-full rounded-lg border border-white/[0.08] bg-[#121218] px-3 text-sm font-semibold text-zinc-100 outline-none transition focus:border-brand/70"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex h-10 items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.035] px-3 text-sm text-zinc-300">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 accent-brand" />
      <span>{label}</span>
    </label>
  );
}

export default function HingedBoxGenerator() {
  const [history, setHistory] = useState<HistoryState>({ past: [], present: DEFAULT_SETTINGS, future: [] });
  const settings = history.present;
  const boxRef = useRef<THREE.Group | null>(null);
  const lidRef = useRef<THREE.Group | null>(null);

  const built = useMemo(() => {
    const box = buildBox(settings);
    const lid = buildLid(settings);
    const boxGroup = cloneMeshesToGroup(box.meshes);
    const lidGroup = cloneMeshesToGroup(lid.meshes);
    boxRef.current = boxGroup;
    lidRef.current = lidGroup;
    return { box: box.group, lid: lid.group, boxExport: boxGroup, lidExport: lidGroup };
  }, [settings]);
  const plateSpacing = Math.max(220, Math.max(settings.length, settings.width) * 1.45);
  const plateSize = Math.max(190, Math.max(settings.length, settings.width) * 1.45);
  const maxPartHeight = Math.max(settings.height, settings.lidThickness + settings.lidLipHeight + settings.hingeDiameter);

  const issues = useMemo(() => validateSettings(settings), [settings]);

  function update(patch: Partial<BoxSettings>) {
    setHistory((state) => ({
      past: [...state.past.slice(-30), state.present],
      present: { ...state.present, ...patch },
      future: [],
    }));
  }

  function setAll(next: BoxSettings) {
    setHistory((state) => ({ past: [...state.past.slice(-30), state.present], present: next, future: [] }));
  }

  function undo() {
    setHistory((state) => {
      const previous = state.past.at(-1);
      if (!previous) return state;
      return { past: state.past.slice(0, -1), present: previous, future: [state.present, ...state.future] };
    });
  }

  function redo() {
    setHistory((state) => {
      const next = state.future[0];
      if (!next) return state;
      return { past: [...state.past, state.present], present: next, future: state.future.slice(1) };
    });
  }

  function exportBox() {
    if (boxRef.current) exportStl("Box.stl", boxRef.current);
  }

  function exportLid() {
    if (lidRef.current) exportStl("Lid.stl", lidRef.current);
  }

  function exportBothZip() {
    if (boxRef.current && lidRef.current) exportZip("AutoSlice-Hinged-Box.zip", boxRef.current, lidRef.current, settings);
  }

  function exportBoth3mf() {
    if (boxRef.current && lidRef.current) exportThreeMf("AutoSlice-Hinged-Box.3mf", boxRef.current, lidRef.current, settings);
  }

  return (
    <div className="min-h-full p-5 lg:p-7">
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-brand">Tools</p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-white">Hinged Box Generator</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={undo} disabled={!history.past.length} className="h-9 rounded-lg border border-white/[0.08] px-3 text-sm font-semibold text-zinc-300 disabled:opacity-40">Undo</button>
          <button onClick={redo} disabled={!history.future.length} className="h-9 rounded-lg border border-white/[0.08] px-3 text-sm font-semibold text-zinc-300 disabled:opacity-40">Redo</button>
          <button onClick={() => setAll(DEFAULT_SETTINGS)} className="h-9 rounded-lg border border-white/[0.08] px-3 text-sm font-semibold text-zinc-300">Reset</button>
          <button onClick={() => setAll(autoCorrect(settings))} className="h-9 rounded-lg bg-brand px-3 text-sm font-bold text-white shadow-[0_0_20px_rgba(224,36,36,0.25)]">Auto-correct</button>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[440px_minmax(0,1fr)]">
        <section className="space-y-4">
          <div className="rounded-xl border border-white/[0.07] bg-[#101015]/92 p-4 shadow-[0_18px_50px_rgba(0,0,0,0.35)]">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.18em] text-zinc-300">Presets</h2>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(PRESETS).map(([name, preset]) => (
                <button
                  key={name}
                  onClick={() => update(preset)}
                  className="min-h-9 rounded-lg border border-white/[0.08] bg-white/[0.035] px-2 text-left text-xs font-semibold text-zinc-300 transition hover:border-brand/60 hover:text-white"
                >
                  {name}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-[#101015]/92 p-4">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.18em] text-zinc-300">Basis</h2>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Lengte" value={settings.length} min={40} max={300} step={1} onChange={(length) => update({ length })} />
              <Field label="Breedte" value={settings.width} min={30} max={220} step={1} onChange={(width) => update({ width })} />
              <Field label="Hoogte" value={settings.height} min={15} max={140} step={1} onChange={(height) => update({ height })} />
              <Field label="Radius" value={settings.radius} min={0} max={25} step={0.5} onChange={(radius) => update({ radius })} />
              <Field label="Bodem" value={settings.bottom} min={0.6} max={8} step={0.1} onChange={(bottom) => update({ bottom })} />
              <Field label="Deksel" value={settings.lidThickness} min={0.6} max={8} step={0.1} onChange={(lidThickness) => update({ lidThickness })} />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <SelectField label="Wanddikte" value={String(settings.wall)} options={WALL_PRESETS.map((value) => ({ value: String(value), label: `${value} mm` }))} onChange={(wall) => update({ wall: Number(wall) })} />
              <SelectField label="Tolerantie" value={String(settings.tolerance)} options={TOLERANCES.map((value) => ({ value: String(value), label: `${value.toFixed(2)} mm` }))} onChange={(tolerance) => update({ tolerance: Number(tolerance) })} />
              <SelectField label="Nozzle" value={String(settings.nozzle)} options={NOZZLES.map((value) => ({ value: String(value), label: `${value} mm` }))} onChange={(nozzle) => update({ nozzle: Number(nozzle) })} />
              <SelectField label="Dekselstijl" value={settings.lidStyle} options={[
                { value: "flat", label: "Flat" },
                { value: "inset", label: "Inset" },
                { value: "overhang", label: "Overhang" },
                { value: "lip", label: "Lip rondom" },
              ]} onChange={(lidStyle) => update({ lidStyle })} />
            </div>
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-[#101015]/92 p-4">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.18em] text-zinc-300">Scharnier & sluiting</h2>
            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Scharnier" value={settings.hingeMode} options={[
                { value: "none", label: "Geen" },
                { value: "two", label: "2 hinges" },
                { value: "three", label: "3 hinges" },
                { value: "continuous", label: "Continuous" },
              ]} onChange={(hingeMode) => update({ hingeMode })} />
              <Field label="Diameter" value={settings.hingeDiameter} min={3} max={14} step={0.1} onChange={(hingeDiameter) => update({ hingeDiameter })} />
              <SelectField label="Pen" value={settings.pinType} options={[
                { value: "filament175", label: "1.75 mm filament" },
                { value: "metal2", label: "2 mm metalen pen" },
                { value: "metal3", label: "3 mm metalen pen" },
                { value: "printed", label: "Printbare pen" },
              ]} onChange={(pinType) => update({ pinType })} />
              <SelectField label="Sluiting" value={settings.latchType} options={[
                { value: "none", label: "Geen" },
                { value: "snap", label: "Kliksluiting" },
                { value: "magnet", label: "Magneetsluiting" },
                { value: "lip", label: "Lip" },
                { value: "slide", label: "Schuifsluiting" },
                { value: "doubleSnap", label: "Dubbele klik" },
              ]} onChange={(latchType) => update({ latchType })} />
            </div>
            <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/20 p-3 text-xs text-zinc-400">
              Pen: {pinDiameter(settings.pinType)} mm · scharnierspeling: {effectiveHingeClearance(settings).toFixed(2)} mm
            </div>
          </div>

          <div className="rounded-xl border border-white/[0.07] bg-[#101015]/92 p-4">
            <h2 className="mb-3 text-sm font-bold uppercase tracking-[0.18em] text-zinc-300">Binnenkant & opties</h2>
            <div className="grid grid-cols-2 gap-3">
              <SelectField label="Compartimenten" value={settings.dividerMode} options={[
                { value: "none", label: "Geen" },
                { value: "horizontal", label: "Horizontaal" },
                { value: "vertical", label: "Verticaal" },
                { value: "grid", label: "Raster" },
              ]} onChange={(dividerMode) => update({ dividerMode })} />
              <Field label="Divider dikte" value={settings.dividerThickness} min={0.6} max={4} step={0.1} onChange={(dividerThickness) => update({ dividerThickness })} />
              <Field label="Rijen" value={settings.dividerRows} min={1} max={8} step={1} onChange={(dividerRows) => update({ dividerRows })} />
              <Field label="Kolommen" value={settings.dividerColumns} min={1} max={10} step={1} onChange={(dividerColumns) => update({ dividerColumns })} />
              <Toggle label="Versterkingsribben" checked={settings.ribs} onChange={(ribs) => update({ ribs })} />
              <Toggle label="Voetjes" checked={settings.feet} onChange={(feet) => update({ feet })} />
              <Toggle label="Ventilatie" checked={settings.ventilation} onChange={(ventilation) => update({ ventilation })} />
              <Toggle label="Stackable" checked={settings.stackable} onChange={(stackable) => update({ stackable })} />
              <Toggle label="Labelhouder" checked={settings.labelHolder} onChange={(labelHolder) => update({ labelHolder })} />
              <Toggle label="Kabeldoorvoer" checked={settings.cablePass} onChange={(cablePass) => update({ cablePass })} />
            </div>
          </div>
        </section>

        <section className="min-h-[720px] overflow-hidden rounded-xl border border-white/[0.07] bg-[#101015]/92 shadow-[0_18px_50px_rgba(0,0,0,0.35)]">
          <div className="flex flex-col gap-3 border-b border-white/[0.06] p-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-zinc-300">Live preview</h2>
              <p className="mt-1 text-xs text-zinc-500">Box en lid worden apart getoond, inclusief passende scharnierdelen.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button onClick={exportBox} className="h-9 rounded-lg border border-white/[0.08] px-3 text-sm font-semibold text-zinc-200">Export Box STL</button>
              <button onClick={exportLid} className="h-9 rounded-lg border border-white/[0.08] px-3 text-sm font-semibold text-zinc-200">Export Lid STL</button>
              <button onClick={exportBothZip} className="h-9 rounded-lg bg-emerald-600 px-3 text-sm font-bold text-white">Export ZIP</button>
              <button onClick={exportBoth3mf} className="h-9 rounded-lg bg-brand px-3 text-sm font-bold text-white">Export 3MF</button>
            </div>
          </div>

          <div className="relative h-[520px] border-b border-white/[0.06]">
            <div className="pointer-events-none absolute z-10 flex w-full justify-center gap-16 pt-4 text-[11px] font-black uppercase tracking-[0.22em] text-zinc-500">
              <span className="rounded-md border border-white/[0.08] bg-black/45 px-3 py-1">Printplaat 1 - Box</span>
              <span className="rounded-md border border-white/[0.08] bg-black/45 px-3 py-1">Printplaat 2 - Lid</span>
            </div>
            <Canvas camera={{ position: [0, 180, 250], fov: 38 }} gl={{ antialias: true }} shadows>
              <color attach="background" args={["#111113"]} />
              <ambientLight intensity={0.45} />
              <directionalLight position={[100, 160, 80]} intensity={1.45} castShadow />
              <directionalLight position={[-80, 50, -70]} intensity={0.32} />
              <PreviewCamera spacing={plateSpacing} plateSize={plateSize} maxPartHeight={maxPartHeight} />
              <Plate x={-plateSpacing / 2} label="BOX" size={plateSize} />
              <Plate x={plateSpacing / 2} label="LID" size={plateSize} />
              <Preview box={built.box} lid={built.lid} spacing={plateSpacing} />
              <OrbitControls makeDefault enableDamping />
            </Canvas>
          </div>

          <div className="grid gap-4 p-4 lg:grid-cols-[1fr_300px]">
            <div>
              <h3 className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-zinc-500">Slimme controles</h3>
              <div className="space-y-2">
                {issues.map((issue, index) => (
                  <div
                    key={`${issue.message}-${index}`}
                    className={[
                      "rounded-lg border px-3 py-2 text-sm",
                      issue.severity === "error" ? "border-red-500/40 bg-red-500/10 text-red-200" :
                      issue.severity === "warning" ? "border-amber-500/35 bg-amber-500/10 text-amber-200" :
                      "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
                    ].join(" ")}
                  >
                    {issue.message}
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-white/[0.06] bg-black/20 p-3">
              <h3 className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-zinc-500">Export info</h3>
              <p className="text-sm leading-relaxed text-zinc-400">
                ZIP bevat aparte STL-bestanden voor box en lid plus printadvies. 3MF bevat dezelfde onderdelen en metadata in een slicer-vriendelijk pakket.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
