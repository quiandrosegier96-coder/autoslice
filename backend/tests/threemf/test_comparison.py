from app.threemf.comparison import compare_packages


def test_semantic_comparison_does_not_require_identical_zip_bytes(core_3mf_bytes):
    comparison = compare_packages(core_3mf_bytes, core_3mf_bytes)
    assert comparison.left.object_count == comparison.right.object_count
    assert comparison.left.mesh_count == comparison.right.mesh_count
    assert comparison.left.package_paths == comparison.right.package_paths
