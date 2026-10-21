"""JJP hotlink audit: pure logic (no MCP / Archicad dependencies).

Rules come from hotlink_standards.md ("稽核參數" section).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

DEFAULT_PARAMS = {
    "linkLayerPrefix": "A-LINK-",
    "maxNodesPerSource": 1,
    "requireLockedLinkLayer": True,
    "networkFilePrefixes": ["T:\\", "\\\\"],
}

_PARAM_LINE = re.compile(r"^-\s*`([^`]+)`\s*:\s*(.+?)\s*$")


def parse_params(markdown: str) -> dict:
    params = dict(DEFAULT_PARAMS)
    in_section = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_section = "稽核參數" in line
            continue
        m = _PARAM_LINE.match(line) if in_section else None
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if key == "maxNodesPerSource":
            params[key] = int(value)
        elif key == "requireLockedLinkLayer":
            params[key] = value.lower() in ("true", "yes", "1", "是")
        elif key == "networkFilePrefixes":
            params[key] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            params[key] = value
    return params


def load_params(path: Path) -> dict:
    return parse_params(path.read_text(encoding="utf-8")) if path.exists() else dict(DEFAULT_PARAMS)


def mask_location(location: str) -> str:
    """Remove BIMcloud credentials (user + JWT) and decode the server/path for display."""
    if not location.startswith("teamwork://"):
        return location
    rest = location[len("teamwork://"):]
    if "@" in rest:
        rest = rest.rsplit("@", 1)[1]  # drop "user:token"
    decoded = rest
    for _ in range(3):  # BIMcloud paths are percent-encoded up to twice
        nxt = unquote(decoded)
        if nxt == decoded:
            break
        decoded = nxt
    return "teamwork://" + decoded


def classify_location(location: str, network_prefixes: list[str]) -> str:
    if location.startswith("teamwork://"):
        return "BIMCLOUD"
    if any(location.upper().startswith(p.upper()) for p in network_prefixes):
        return "NETWORK_FILE"
    return "LOCAL_FILE"


@dataclass
class SourceSummary:
    source: str
    kind: str
    nodes: list[dict] = field(default_factory=list)
    nested: list[str] = field(default_factory=list)

    def status(self, max_nodes: int) -> list[str]:
        flags = []
        if self.kind == "LOCAL_FILE":
            flags.append("VIOLATION_LOCAL_PATH")
        if self.kind == "NETWORK_FILE":
            flags.append("WARN_NETWORK_FILE")
        if self.nested:
            flags.append("VIOLATION_NESTED")
        if len(self.nodes) > max_nodes:
            flags.append("REVIEW_MULTIPLE_NODES")
        return flags or ["OK"]


def summarise_nodes(hotlinks: list[dict], network_prefixes: list[str]) -> dict[str, SourceSummary]:
    """Group top-level hotlink nodes by source file; record nested children."""
    sources: dict[str, SourceSummary] = {}

    def nested_names(node: dict) -> list[str]:
        out = []
        for child in node.get("children") or []:
            out.append(mask_location(child.get("location", "")))
            out.extend(nested_names(child))
        return out

    for node in hotlinks:
        loc = node.get("location", "")
        key = mask_location(loc)
        s = sources.setdefault(key, SourceSummary(source=key, kind=classify_location(loc, network_prefixes)))
        s.nodes.append({"guid": (node.get("hotlinkNodeId") or {}).get("guid"), "name": node.get("name")})
        s.nested.extend(nested_names(node))
    return sources


def audit_instance_layers(layer_names: list[str], locked: dict[str, bool], prefix: str, require_locked: bool) -> dict:
    off_layer = [n for n in layer_names if not n.startswith(prefix)]
    used = sorted(set(layer_names))
    unlocked = [n for n in used if n.startswith(prefix) and not locked.get(n, False)] if require_locked else []
    return {
        "instanceCount": len(layer_names),
        "layersUsed": {n: layer_names.count(n) for n in used},
        "instancesNotOnLinkLayer": len(off_layer),
        "unlockedLinkLayers": unlocked,
    }
