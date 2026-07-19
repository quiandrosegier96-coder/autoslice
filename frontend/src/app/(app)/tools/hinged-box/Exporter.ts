import * as THREE from "three";
import { STLExporter } from "three/examples/jsm/exporters/STLExporter.js";
import { BoxSettings, effectiveHingeClearance, pinDiameter } from "./Presets";

const encoder = new TextEncoder();

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function objectToStl(object: THREE.Object3D) {
  const exporter = new STLExporter();
  const result = exporter.parse(object, { binary: false });
  return typeof result === "string" ? result : new TextDecoder().decode(result);
}

export function exportStl(filename: string, object: THREE.Object3D) {
  downloadBlob(filename, new Blob([objectToStl(object)], { type: "model/stl" }));
}

export function exportThreeMf(filename: string, box: THREE.Object3D, lid: THREE.Object3D, settings: BoxSettings) {
  const model = objectsToThreeMfModel([
    { id: 1, name: "Box", object: box },
    { id: 2, name: "Lid", object: lid },
  ]);
  downloadBlob(filename, makeZip([
    { name: "[Content_Types].xml", data: encoder.encode(`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>`) },
    { name: "_rels/.rels", data: encoder.encode(`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>`) },
    { name: "3D/3dmodel.model", data: encoder.encode(model) },
    { name: "AutoSlice_Readme.txt", data: encoder.encode(readme(settings)) },
  ], "model/3mf"));
}

export function exportZip(filename: string, box: THREE.Object3D, lid: THREE.Object3D, settings: BoxSettings) {
  downloadBlob(filename, makeZip([
    { name: "Box.stl", data: encoder.encode(objectToStl(box)) },
    { name: "Lid.stl", data: encoder.encode(objectToStl(lid)) },
    { name: "Readme.txt", data: encoder.encode(readme(settings)) },
  ], "application/zip"));
}

function readme(settings: BoxSettings) {
  return [
    "AutoSlice Hinged Box Generator",
    "",
    `Outer size: ${settings.length} x ${settings.width} x ${settings.height} mm`,
    `Wall thickness: ${settings.wall} mm`,
    `Bottom thickness: ${settings.bottom} mm`,
    `Lid thickness: ${settings.lidThickness} mm`,
    `Tolerance: ${settings.tolerance} mm`,
    `Nozzle: ${settings.nozzle} mm`,
    `Hinge: ${settings.hingeMode}`,
    `Hinge diameter: ${settings.hingeDiameter} mm`,
    `Pin diameter: ${pinDiameter(settings.pinType)} mm`,
    `Hinge clearance: ${effectiveHingeClearance(settings).toFixed(2)} mm`,
    `Latch: ${settings.latchType}`,
    "",
    "Print orientation:",
    "- Box: bottom on build plate, open side up.",
    "- Lid: outside top face on build plate for strongest lip, or rotate top-up for best surface finish.",
    "",
    "Filament advice:",
    "- PLA/PETG work well.",
    "- Print hinge barrels slowly with 3+ perimeters.",
    "- Test pin fit before forcing the hinge together.",
  ].join("\n");
}

type ZipFile = { name: string; data: Uint8Array };

function makeZip(files: ZipFile[], type = "application/zip") {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;

  files.forEach((file) => {
    const name = encoder.encode(file.name.replace(/\\/g, "/"));
    const crc = crc32(file.data);
    const local = concat([
      u32(0x04034b50), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(crc), u32(file.data.length), u32(file.data.length), u16(name.length), u16(0),
      name, file.data,
    ]);
    localParts.push(local);
    centralParts.push(concat([
      u32(0x02014b50), u16(20), u16(20), u16(0), u16(0), u16(0), u16(0),
      u32(crc), u32(file.data.length), u32(file.data.length), u16(name.length), u16(0), u16(0),
      u16(0), u16(0), u32(0), u32(offset), name,
    ]));
    offset += local.length;
  });

  const centralOffset = offset;
  const central = concat(centralParts);
  const end = concat([
    u32(0x06054b50), u16(0), u16(0), u16(files.length), u16(files.length),
    u32(central.length), u32(centralOffset), u16(0),
  ]);
  const bytes = concat([...localParts, central, end]);
  const arrayBuffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
  return new Blob([arrayBuffer], { type });
}

function u16(value: number) {
  const bytes = new Uint8Array(2);
  new DataView(bytes.buffer).setUint16(0, value, true);
  return bytes;
}

function u32(value: number) {
  const bytes = new Uint8Array(4);
  new DataView(bytes.buffer).setUint32(0, value >>> 0, true);
  return bytes;
}

function concat(parts: Uint8Array[]) {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  parts.forEach((part) => {
    out.set(part, offset);
    offset += part.length;
  });
  return out;
}

function crc32(data: Uint8Array) {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i += 1) {
    crc ^= data[i];
    for (let j = 0; j < 8; j += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

type ThreeMfObject = {
  id: number;
  name: string;
  object: THREE.Object3D;
};

function objectsToThreeMfModel(objects: ThreeMfObject[]) {
  const resources = objects.map(({ id, name, object }) => {
    const mesh = objectToThreeMfMesh(object);
    return `    <object id="${id}" name="${escapeXml(name)}" type="model">
      <mesh>
        <vertices>
${mesh.vertices}
        </vertices>
        <triangles>
${mesh.triangles}
        </triangles>
      </mesh>
    </object>`;
  }).join("\n");

  const build = objects.map(({ id }) => `    <item objectid="${id}" />`).join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Title">AutoSlice Hinged Box</metadata>
  <metadata name="Designer">AutoSlice</metadata>
  <metadata name="Description">Parametric hinged box with separate printable box and lid.</metadata>
  <resources>
${resources}
  </resources>
  <build>
${build}
  </build>
</model>`;
}

function objectToThreeMfMesh(object: THREE.Object3D) {
  object.updateMatrixWorld(true);
  const vertices: string[] = [];
  const triangles: string[] = [];
  let vertexOffset = 0;

  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;

    const geometry = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry.clone();
    const position = geometry.getAttribute("position");
    const normal = new THREE.Matrix3().getNormalMatrix(mesh.matrixWorld);
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    const c = new THREE.Vector3();

    for (let i = 0; i < position.count; i += 3) {
      a.fromBufferAttribute(position, i).applyMatrix4(mesh.matrixWorld);
      b.fromBufferAttribute(position, i + 1).applyMatrix4(mesh.matrixWorld);
      c.fromBufferAttribute(position, i + 2).applyMatrix4(mesh.matrixWorld);

      const ab = new THREE.Vector3().subVectors(b, a);
      const ac = new THREE.Vector3().subVectors(c, a);
      const cross = new THREE.Vector3().crossVectors(ab, ac).applyMatrix3(normal);
      const order = cross.lengthSq() > 0 && cross.y < 0 ? [a, c, b] : [a, b, c];

      order.forEach((vertex) => {
        vertices.push(`          <vertex x="${fmt(vertex.x)}" y="${fmt(vertex.y)}" z="${fmt(vertex.z)}" />`);
      });
      triangles.push(`          <triangle v1="${vertexOffset}" v2="${vertexOffset + 1}" v3="${vertexOffset + 2}" />`);
      vertexOffset += 3;
    }
    geometry.dispose();
  });

  return {
    vertices: vertices.join("\n"),
    triangles: triangles.join("\n"),
  };
}

function fmt(value: number) {
  return Number.isFinite(value) ? value.toFixed(4).replace(/\.?0+$/, "") : "0";
}

function escapeXml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
