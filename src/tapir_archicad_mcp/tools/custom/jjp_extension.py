"""JJP extension: BIM standard (DP-018A) audit tools and workspace resources.

Ported from the 0.4-based fork onto upstream tapir-archicad-mcp 0.6.6. The
original module's source had been corrupted (invalid UTF-8) and never loaded;
the layer table now comes from layer_standards.md via jjp_standards.
Read-only: these tools never modify the Archicad project.
"""

import json
import logging
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from multiconn_archicad import ConnHeader, Port

from tapir_archicad_mcp.app import mcp
from tapir_archicad_mcp.context import multi_conn_instance
from tapir_archicad_mcp.tools.custom import jjp_standards as std

log = logging.getLogger(__name__)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _get_header(port: int) -> ConnHeader:
    try:
        return multi_conn_instance.get().active[Port(port)]
    except KeyError:
        raise ToolError(f"Port {port} is not an active Archicad connection.") from None


def _project_name(header: ConnHeader) -> str:
    return getattr(header.archicad_id, "projectName", "Unknown")


def _read_text(path: Path, missing: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else missing


# --- Resources ---------------------------------------------------------------

@mcp.resource("jjp://workspace/workflow_config")
def get_workflow_config() -> str:
    """JJP Architect CTO workflow configuration (JSON)."""
    path = std.workflow_config_path()
    return _read_text(path, f"Error: configuration file not found at {path}")


@mcp.resource("jjp://workspace/standards")
def get_jjp_standards() -> str:
    """JJP BIM standards (DP-018A): layer and property standards as Markdown."""
    ref = std.standards_dir()
    return (
        "# JJP Architects & Planners BIM Standards (DP-018A)\n\n"
        + _read_text(ref / "layer_standards.md", "Layer standards reference not found.\n")
        + "\n\n"
        + _read_text(ref / "property_standards.md", "Property standards reference not found.\n")
    )


# --- Workspace tools ---------------------------------------------------------

@mcp.tool(
    name="jjp_get_transformation_config",
    title="Get JJP Transformation Config",
    description=(
        "Loads the Architect_CTO_Workflow.mcp.json file (path configurable via JJP_WORKFLOW_CONFIG), "
        "which lists paths to goals, objectives, strategy, standards and operational rules."
    ),
    annotations=READ_ONLY,
)
def jjp_get_transformation_config() -> dict:
    path = std.workflow_config_path()
    if not path.exists():
        raise ToolError(f"Configuration file not found at {path}. Set JJP_WORKFLOW_CONFIG to its location.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ToolError(f"Failed to parse workflow config {path}: {e}") from e


@mcp.tool(
    name="jjp_read_resource_path",
    title="Browse JJP Transformation Resources",
    description=(
        "Lists files under a digital-transformation resource directory defined in the workflow config. "
        "resource_name examples: PLAN_GOALS, PLAN_OBJECTIVES, PLAN_TEMPLATE, STRATEGY, STANDARDS, "
        "PROJECTS, TECH_R_D, INFRASTRUCTURE, KNOWLEDGE."
    ),
    annotations=READ_ONLY,
)
def jjp_read_resource_path(resource_name: str) -> dict:
    config = jjp_get_transformation_config()
    definitions = config.get("definitions", {})
    if resource_name not in definitions:
        raise ToolError(f"'{resource_name}' is not defined. Available: {sorted(definitions)}")

    entry = definitions[resource_name]
    rel_path = entry.get("path", "")
    target = Path(config.get("workspace_root", "D:/")) / rel_path
    if not target.exists():
        target = Path(rel_path)
    if not target.exists():
        return {"resource_name": resource_name, "configured_path": rel_path, "status": "NOT_FOUND"}

    items = [
        {"name": c.name, "is_directory": c.is_dir(), "size_bytes": c.stat().st_size if c.is_file() else None}
        for c in target.iterdir()
    ]
    return {
        "resource_name": resource_name,
        "description": entry.get("description"),
        "resolved_absolute_path": str(target.resolve()),
        "status": "FOUND",
        "items": items,
    }


# --- Audit tools -------------------------------------------------------------

@mcp.tool(
    name="jjp_audit_layers",
    title="JJP BIM Layer Audit (DP-018A)",
    description=(
        "Audits every layer of the Archicad project on the given port against JJP standard DP-018A "
        "(standard names from layer_standards.md, allowed prefixes A-/S-/L-/G-). Read-only."
    ),
    annotations=READ_ONLY,
)
def jjp_audit_layers(port: int) -> dict:
    header = _get_header(port)
    try:
        standards = std.load_layer_standards()
    except OSError as e:
        raise ToolError(f"Cannot read layer standards: {e}. Set JJP_STANDARDS_DIR.") from e

    ids = header.core.post_command("API.GetAttributesByType", {"attributeType": "Layer"}).get("attributeIds", [])
    attributes = (
        header.core.post_command("API.GetLayerAttributes", {"attributeIds": ids}).get("attributes", []) if ids else []
    )
    layers = []
    for item in attributes:
        layer = item.get("layerAttribute")
        if layer:
            layers.append({
                "name": layer.get("name", ""),
                "guid": layer.get("attributeId", {}).get("guid"),
                "isLocked": layer.get("isLocked", False),
                "isHidden": layer.get("isHidden", False),
            })

    result = std.audit_layers(layers, standards)
    missing = sorted(set(standards) - {layer["name"] for layer in layers})
    order = {"VIOLATION_PREFIX": 0, "CUSTOM_VALID": 1, "CONFORMING": 2, "SYSTEM_LAYER": 3}
    return {
        "port": port,
        "projectName": _project_name(header),
        "layerCount": result.total,
        "standardLayerCount": len(standards),
        "conformingCount": result.conforming,
        "customCount": result.custom,
        "violationCount": result.violations,
        "systemCount": result.system,
        "complianceRate": f"{result.compliance_rate:.1%}",
        "standardLayersMissing": missing,
        "details": sorted(result.details, key=lambda d: (order[d["status"]], d["name"])),
    }


@mcp.tool(
    name="jjp_audit_properties",
    title="JJP BIM Property Group Audit",
    description=(
        "Audits user-defined property definitions of the Archicad project on the given port: JJP data must "
        "sit in groups prefixed <<JJP>>, <TAI> or <AC>. Read-only."
    ),
    annotations=READ_ONLY,
)
def jjp_audit_properties(port: int) -> dict:
    header = _get_header(port)
    props = header.core.post_command("API.GetAllPropertyIds", {"propertyType": "UserDefined"}).get("properties", [])
    definitions = (
        header.core.post_command("API.GetDetailsOfProperties", {"properties": props}).get("propertyDefinitions", [])
        if props else []
    )

    details = []
    counts = {"JJP_CONFORMING": 0, "NON_STANDARD_JJP_GROUP": 0, "OTHER_GROUP": 0}
    for item in definitions:
        prop = item.get("propertyDefinition")
        if not prop:
            continue
        group = prop.get("group", {})
        status, description = std.classify_property_group(group.get("name", ""))
        counts[status] += 1
        details.append({
            "name": prop.get("name", ""),
            "guid": prop.get("propertyId", {}).get("guid"),
            "group": group.get("name", ""),
            "type": prop.get("type", ""),
            "status": status,
            "description": description,
        })

    return {
        "port": port,
        "projectName": _project_name(header),
        "totalProperties": len(details),
        "jjpConforming": counts["JJP_CONFORMING"],
        "nonStandardJjpGroups": counts["NON_STANDARD_JJP_GROUP"],
        "otherGroups": counts["OTHER_GROUP"],
        "details": sorted(details, key=lambda d: (d["status"] != "NON_STANDARD_JJP_GROUP", d["group"], d["name"])),
    }
