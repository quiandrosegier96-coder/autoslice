"""Deterministic Universal3MF release benchmark (time and Python peak memory)."""

from __future__ import annotations

from io import BytesIO
import json
import statistics
import time
import tracemalloc
import zipfile

from app.threemf.conversion import convert_3mf
from app.threemf.domain.settings import ConversionContext


CASES = (
    ("small", 12, 1, 1),
    ("medium", 1_000, 1, 1),
    ("large", 10_000, 1, 1),
    ("multicolor", 1_000, 1, 4),
    ("multi-object", 1_000, 8, 1),
)


def package(triangle_count: int, object_count: int, materials: int) -> bytes:
    per_object = max(1, triangle_count // object_count)
    objects: list[str] = []
    build: list[str] = []
    for object_index in range(object_count):
        vertices: list[str] = []
        triangles: list[str] = []
        for index in range(per_object):
            x = index % 100
            y = (index // 100) % 100
            base = index * 3
            vertices.extend(
                (
                    f'<vertex x="{x}" y="{y}" z="0"/>',
                    f'<vertex x="{x + 0.8}" y="{y}" z="0"/>',
                    f'<vertex x="{x}" y="{y + 0.8}" z="{(index % 7) * 0.1}"/>',
                )
            )
            triangles.append(
                f'<triangle v1="{base}" v2="{base + 1}" v3="{base + 2}" p1="{index % materials}"/>'
            )
        object_id = object_index + 1
        objects.append(
            f'<object id="{object_id}" type="model" pid="50"><mesh><vertices>{"".join(vertices)}</vertices><triangles>{"".join(triangles)}</triangles></mesh></object>'
        )
        build.append(f'<item objectid="{object_id}" transform="1 0 0 0 1 0 0 0 1 {object_index * 120} 0 0"/>')
    colors = "".join(
        f'<base name="Material {index + 1}" displaycolor="#{index * 40:02X}55AAFF"/>'
        for index in range(materials)
    )
    model = (
        '<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        '<metadata name="Application">Bambu Studio</metadata><resources>'
        f'<basematerials id="50">{colors}</basematerials>{"".join(objects)}</resources>'
        f'<build>{"".join(build)}</build></model>'
    ).encode()
    rels = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("_rels/.rels", rels)
        archive.writestr("3D/3dmodel.model", model)
    return output.getvalue()


def main() -> None:
    context = ConversionContext("anycubic", "kobra_s1_combo", 0.4, "pla")
    results: list[dict[str, object]] = []
    for name, triangles, objects, materials in CASES:
        payload = package(triangles, objects, materials)
        samples: list[float] = []
        peaks: list[float] = []
        output_size = 0
        for _ in range(3):
            tracemalloc.start()
            started = time.perf_counter()
            result = convert_3mf(payload, context, original_filename=f"{name}.3mf")
            samples.append((time.perf_counter() - started) * 1_000)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks.append(peak / (1024 * 1024))
            output_size = len(result.output)
        results.append(
            {
                "case": name,
                "triangles": triangles,
                "objects": objects,
                "materials": materials,
                "input_bytes": len(payload),
                "output_bytes": output_size,
                "median_ms": round(statistics.median(samples), 2),
                "max_peak_python_mb": round(max(peaks), 2),
            }
        )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
