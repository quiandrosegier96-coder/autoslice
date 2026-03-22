import * as THREE from "three";

export type OverhangFace = {
  faceIndex: number;
  center:    THREE.Vector3;
  normal:    THREE.Vector3;
};

export function detectOverhangFaces(
  geometry: THREE.BufferGeometry,
  angleDeg  = 50,
): OverhangFace[] {
  const overhangFaces: OverhangFace[] = [];

  const pos       = geometry.attributes.position;
  const index     = geometry.index;
  const threshold = Math.cos(THREE.MathUtils.degToRad(angleDeg));
  const up        = new THREE.Vector3(0, 1, 0);

  const a      = new THREE.Vector3();
  const b      = new THREE.Vector3();
  const c      = new THREE.Vector3();
  const ab     = new THREE.Vector3();
  const ac     = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const center = new THREE.Vector3();

  const faceCount = index ? index.count / 3 : pos.count / 3;

  for (let i = 0; i < faceCount; i++) {
    const i0 = index ? index.getX(i * 3 + 0) : i * 3 + 0;
    const i1 = index ? index.getX(i * 3 + 1) : i * 3 + 1;
    const i2 = index ? index.getX(i * 3 + 2) : i * 3 + 2;

    a.fromBufferAttribute(pos, i0);
    b.fromBufferAttribute(pos, i1);
    c.fromBufferAttribute(pos, i2);

    ab.subVectors(b, a);
    ac.subVectors(c, a);
    normal.crossVectors(ab, ac).normalize();

    // Only faces pointing downward past the threshold
    if (normal.dot(up) < -threshold) {
      center.copy(a).add(b).add(c).multiplyScalar(1 / 3);

      overhangFaces.push({
        faceIndex: i,
        center:    center.clone(),
        normal:    normal.clone(),
      });
    }
  }

  return overhangFaces;
}
