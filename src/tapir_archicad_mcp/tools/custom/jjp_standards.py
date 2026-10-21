"""JJP BIM standards (DP-018A): pure logic with no MCP / Archicad dependencies.

The layer and property standards are read from the jjp-compliance-expert skill
references, so the Markdown files stay the single source of truth.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_WORKSPACE_ROOT = "D:/20_Digital_Transformation"


def workspace_root() -> Path:
    return Path(os.getenv("JJP_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT))


def standards_dir() -> Path:
    default = workspace_root() / ".gemini" / "skills" / "jjp-compliance-expert" / "references"
    return Path(os.getenv("JJP_STANDARDS_DIR", str(default)))


def workflow_config_path() -> Path:
    default = workspace_root() / "05_Workspace_Dev" / "Architect_CTO_Workflow.mcp.json"
    return Path(os.getenv("JJP_WORKFLOW_CONFIG", str(default)))


ALLOWED_LAYER_PREFIXES = ("A-", "S-", "L-", "G-")
JJP_PROPERTY_GROUP_PREFIXES = ("<<JJP>>", "<TAI>", "<AC>")

# "- `A-CLNG`: 天花版 / 天花物件"
_LAYER_LINE = re.compile(r"^-\s*`([^`]+)`\s*:\s*(.+?)\s*$")
# "- `G-GB-雨水`, `G-GB-保水`, `G-GB-綠化` 等"
_CODE = re.compile(r"`([^`]+)`")


def _is_layer_code(code: str) -> bool:
    # Prefix declarations ("A-") and suffix notes (".2D", "(說明)") are not layers.
    return not code.endswith("-") and not code.startswith((".", "(", "（"))


def _section_codes(markdown: str, heading_filter) -> list[tuple[str, str]]:
    """Return (section heading, code) for backticked codes on bullet lines in matching sections."""
    out, section = [], ""
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        if line.startswith("-") and heading_filter(section):
            match = _CODE.search(line)
            if match:
                out.append((section, match.group(1)))
    return out


def parse_allowed_layer_prefixes(markdown: str) -> tuple[str, ...]:
    """Prefixes declared in a section whose heading contains '前綴' (codes ending in '-')."""
    found = tuple(c for _, c in _section_codes(markdown, lambda s: "前綴" in s) if c.endswith("-"))
    return found or ALLOWED_LAYER_PREFIXES


def parse_property_prefixes(markdown: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(JJP group prefixes, external-standard group prefixes) from '前綴' sections."""
    jjp, external = [], []
    for section, code in _section_codes(markdown, lambda s: "前綴" in s):
        (external if "外部" in section else jjp).append(code)
    return (tuple(jjp) or JJP_PROPERTY_GROUP_PREFIXES, tuple(external))


def parse_layer_standards(markdown: str) -> dict[str, str]:
    """Parse layer_standards.md into {layer name: description}."""
    layers: dict[str, str] = {}
    section = ""
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.startswith("-"):
            continue
        match = _LAYER_LINE.match(line)
        if match:
            if _is_layer_code(match.group(1)):
                layers[match.group(1)] = match.group(2)
            continue
        for code in _CODE.findall(line):
            if _is_layer_code(code):
                layers.setdefault(code, section)
    return layers


def load_layer_standards(path: Path | None = None) -> dict[str, str]:
    path = path or standards_dir() / "layer_standards.md"
    return parse_layer_standards(path.read_text(encoding="utf-8"))


def load_allowed_layer_prefixes(path: Path | None = None) -> tuple[str, ...]:
    path = path or standards_dir() / "layer_standards.md"
    return parse_allowed_layer_prefixes(path.read_text(encoding="utf-8")) if path.exists() else ALLOWED_LAYER_PREFIXES


def load_property_prefixes(path: Path | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    path = path or standards_dir() / "property_standards.md"
    if not path.exists():
        return JJP_PROPERTY_GROUP_PREFIXES, ()
    return parse_property_prefixes(path.read_text(encoding="utf-8"))


@dataclass
class LayerAuditResult:
    details: list[dict] = field(default_factory=list)
    conforming: int = 0
    variant: int = 0
    custom: int = 0
    violations: int = 0
    system: int = 0

    @property
    def total(self) -> int:
        return len(self.details)

    @property
    def compliance_rate(self) -> float:
        return (self.conforming + self.variant + self.custom + self.system) / self.total if self.total else 1.0


# Suffix conventions used in the JJP template: "A-OBJE.3D", "A-FLOOR(地坪)", "S-BEAM.平面隱藏"
_SUFFIX = re.compile(r"[.(（].*$")


def base_layer_name(name: str) -> str:
    """Strip a display/usage suffix: 'A-OBJE.3D' -> 'A-OBJE', 'A-FLOOR(地坪)' -> 'A-FLOOR'."""
    return _SUFFIX.sub("", name).strip()


def audit_layer(
    name: str, standards: dict[str, str], prefixes: tuple[str, ...] = ALLOWED_LAYER_PREFIXES
) -> tuple[str, str]:
    """Return (status, description) for one layer name."""
    if "archicad" in name.lower():
        return "SYSTEM_LAYER", "Built-in Archicad system layer"
    if name in standards:
        return "CONFORMING", standards[name]
    base = base_layer_name(name)
    if base != name and base in standards:
        return "CONFORMING_VARIANT", f"Variant of standard layer {base}: {standards[base]}"
    if name.startswith(prefixes):
        return "CUSTOM_VALID", "Custom layer with a standard JJP prefix (allowed, review before adding to template)"
    return "VIOLATION_PREFIX", f"Must start with one of {list(prefixes)}"


def audit_layers(
    layers: list[dict], standards: dict[str, str], prefixes: tuple[str, ...] = ALLOWED_LAYER_PREFIXES
) -> LayerAuditResult:
    """layers: [{"name", "guid", "isLocked", "isHidden"}]"""
    result = LayerAuditResult()
    for layer in layers:
        status, description = audit_layer(layer.get("name", ""), standards, prefixes)
        if status == "SYSTEM_LAYER":
            result.system += 1
        elif status == "CONFORMING":
            result.conforming += 1
        elif status == "CONFORMING_VARIANT":
            result.variant += 1
        elif status == "CUSTOM_VALID":
            result.custom += 1
        else:
            result.violations += 1
        result.details.append({**layer, "status": status, "description": description})
    return result


def classify_property_group(
    group_name: str,
    jjp_prefixes: tuple[str, ...] = JJP_PROPERTY_GROUP_PREFIXES,
    external_prefixes: tuple[str, ...] = (),
) -> tuple[str, str]:
    if group_name.startswith(jjp_prefixes):
        return "JJP_CONFORMING", "Standard JJP property group"
    if external_prefixes and group_name.startswith(external_prefixes):
        return "EXTERNAL_STANDARD", "Allowed external / built-in standard group (COBie, LCA, ...)"
    lowered = group_name.lower()
    if "jjp" in lowered or "tai" in lowered:
        return "NON_STANDARD_JJP_GROUP", (
            f"Looks like a JJP group but lacks a standard prefix {list(jjp_prefixes)}"
        )
    return "OTHER_GROUP", "Built-in or generic property group"
