"""OPC relationship helpers shared by detection, parsing, and validation."""

from app.threemf.container.reader import ThreeMFContainer
from app.threemf.container.security import UnsafeThreeMFError, normalized_member_name
from app.threemf.container.xml import local_name, parse_xml

THREEMF_RELATIONSHIP = "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"


def primary_model_path(container: ThreeMFContainer) -> str:
    if container.exists("_rels/.rels"):
        root = parse_xml(container.read("_rels/.rels"), "_rels/.rels")
        for relationship in root:
            if local_name(relationship.tag) == "Relationship" and relationship.attrib.get("Type") == THREEMF_RELATIONSHIP:
                if relationship.attrib.get("TargetMode", "Internal").lower() == "external":
                    raise UnsafeThreeMFError("External primary-model relationships are not allowed.")
                raw_target = relationship.attrib.get("Target", "")
                target = normalized_member_name(raw_target.lstrip("/")) if raw_target else ""
                if target and container.exists(target):
                    return target
    if container.exists("3D/3dmodel.model"):
        return "3D/3dmodel.model"
    raise ValueError("3MF package has no reachable primary model part.")
