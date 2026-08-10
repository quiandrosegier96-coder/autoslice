"""Small hardened XML entry point for uploaded package data."""

import xml.etree.ElementTree as ET

from app.threemf.container.security import UnsafeThreeMFError

MAX_XML_BYTES = 32 * 1024 * 1024


def parse_xml(payload: bytes, path: str = "<memory>") -> ET.Element:
    if len(payload) > MAX_XML_BYTES:
        raise UnsafeThreeMFError(f"XML part exceeds the {MAX_XML_BYTES}-byte safety limit: {path}")
    prefix = payload[:4096].lower()
    if b"<!doctype" in prefix or b"<!entity" in prefix:
        raise UnsafeThreeMFError(f"DTD/entity declarations are not allowed in {path}.")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML in {path}: {exc}") from exc


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
