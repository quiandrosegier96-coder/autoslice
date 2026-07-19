import * as THREE from "three";

export type MeshBuild = {
  group: THREE.Group;
  meshes: THREE.Mesh[];
};

export const RED_MATERIAL = new THREE.MeshStandardMaterial({
  color: "#d71920",
  roughness: 0.58,
  metalness: 0.08,
});

export const LID_MATERIAL = new THREE.MeshStandardMaterial({
  color: "#ef4444",
  roughness: 0.5,
  metalness: 0.08,
});

export const HINGE_MATERIAL = new THREE.MeshStandardMaterial({
  color: "#a3e635",
  roughness: 0.45,
  metalness: 0.05,
});

export const ACCENT_MATERIAL = new THREE.MeshStandardMaterial({
  color: "#22c55e",
  roughness: 0.55,
  metalness: 0.05,
});

export function roundedBoxGeometry(width: number, height: number, depth: number, radius: number, segments = 8) {
  const shape = roundedRectShape(width, depth, Math.min(radius, width / 2 - 0.1, depth / 2 - 0.1));
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: height,
    bevelEnabled: false,
    curveSegments: segments,
  });
  geometry.rotateX(Math.PI / 2);
  geometry.translate(0, height / 2, 0);
  geometry.computeVertexNormals();
  return geometry;
}

export function roundedRectShape(width: number, depth: number, radius: number) {
  const x = -width / 2;
  const y = -depth / 2;
  const r = Math.max(0, Math.min(radius, width / 2 - 0.1, depth / 2 - 0.1));
  const shape = new THREE.Shape();
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + depth - r);
  shape.quadraticCurveTo(x + width, y + depth, x + width - r, y + depth);
  shape.lineTo(x + r, y + depth);
  shape.quadraticCurveTo(x, y + depth, x, y + depth - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  return shape;
}

export function makeMesh(geometry: THREE.BufferGeometry, material: THREE.Material, name: string) {
  const mesh = new THREE.Mesh(geometry, material.clone());
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

export function cylinderBetween(
  start: THREE.Vector3,
  end: THREE.Vector3,
  radius: number,
  material: THREE.Material,
  name: string,
  radialSegments = 24,
) {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();
  const geometry = new THREE.CylinderGeometry(radius, radius, length, radialSegments, 1, false);
  const mesh = makeMesh(geometry, material, name);
  const midpoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  mesh.position.copy(midpoint);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  return mesh;
}

export function addBox(
  group: THREE.Group,
  meshes: THREE.Mesh[],
  size: [number, number, number],
  position: [number, number, number],
  material: THREE.Material,
  name: string,
  radius = 0,
) {
  const geometry = radius > 0
    ? roundedBoxGeometry(size[0], size[1], size[2], radius)
    : new THREE.BoxGeometry(size[0], size[1], size[2]);
  const mesh = makeMesh(geometry, material, name);
  mesh.position.set(position[0], position[1], position[2]);
  group.add(mesh);
  meshes.push(mesh);
  return mesh;
}

export function cloneMeshesToGroup(meshes: THREE.Mesh[]) {
  const group = new THREE.Group();
  meshes.forEach((mesh) => {
    const clone = mesh.clone();
    clone.geometry = mesh.geometry.clone();
    group.add(clone);
  });
  return group;
}

export function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry?.dispose();
    const material = mesh.material;
    if (Array.isArray(material)) material.forEach((m) => m.dispose());
    else material?.dispose();
  });
}
