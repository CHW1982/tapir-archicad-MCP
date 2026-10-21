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
    multi_conn = multi_conn_instance.get()
    if Port(port) not in multi_conn.active:
        # After a server restart nothing is connected until a scan; do it on demand.
        multi_conn.refresh.all_ports()
        multi_conn.connect.all()
    try:
        return multi_conn.active[Port(port)]
    except KeyError:
        raise ToolError(f"Port {port} is not an active Archicad connection.") from None


def _project_name(header: ConnHeader) -> str:
    return getattr(header.archicad_id, "projectName", "Unknown")


def _read_text(path: Path, missing: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else missing


def _summarise_groups(details: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for d in details:
        g = groups.setdefault(d["group"], {"group": d["group"], "status": d["status"], "propertyCount": 0})
        g["propertyCount"] += 1
    return sorted(groups.values(), key=lambda g: (g["status"], g["group"]))


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
        prefixes = std.load_allowed_layer_prefixes()
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

    result = std.audit_layers(layers, standards, prefixes)
    present = {std.base_layer_name(layer["name"]) for layer in layers} | {layer["name"] for layer in layers}
    missing = sorted(set(standards) - present)
    order = {"VIOLATION_PREFIX": 0, "CUSTOM_VALID": 1, "CONFORMING_VARIANT": 2, "CONFORMING": 3, "SYSTEM_LAYER": 4}
    return {
        "port": port,
        "projectName": _project_name(header),
        "layerCount": result.total,
        "standardLayerCount": len(standards),
        "allowedPrefixes": list(prefixes),
        "standardsFile": str(std.standards_dir() / "layer_standards.md"),
        "conformingCount": result.conforming,
        "conformingVariantCount": result.variant,
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
    props = header.core.post_command("API.GetAllPropertyIds", {"propertyType": "UserDefined"}).get("propertyIds", [])
    definitions = (
        header.core.post_command("API.GetDetailsOfProperties", {"properties": props}).get("propertyDefinitions", [])
        if props else []
    )

    jjp_prefixes, external_prefixes = std.load_property_prefixes()
    details = []
    counts = {"JJP_CONFORMING": 0, "EXTERNAL_STANDARD": 0, "NON_STANDARD_JJP_GROUP": 0, "OTHER_GROUP": 0}
    for item in definitions:
        prop = item.get("propertyDefinition")
        if not prop:
            continue
        group = prop.get("group", {})
        status, description = std.classify_property_group(group.get("name", ""), jjp_prefixes, external_prefixes)
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
        "jjpPrefixes": list(jjp_prefixes),
        "externalPrefixes": list(external_prefixes),
        "jjpConforming": counts["JJP_CONFORMING"],
        "externalStandard": counts["EXTERNAL_STANDARD"],
        "nonStandardJjpGroups": counts["NON_STANDARD_JJP_GROUP"],
        "otherGroups": counts["OTHER_GROUP"],
        "groups": _summarise_groups(details),
        "flagged": [d for d in details if d["status"] in ("NON_STANDARD_JJP_GROUP", "OTHER_GROUP")],
    }


# --- Localization export -----------------------------------------------------

# Element types accepted by API.GetElementsByType (Archicad 28 JSON API).
_ELEMENT_TYPES = [
    "Wall", "Column", "Beam", "Window", "Door", "Object", "Lamp", "Slab", "Roof", "Mesh",
    "Dimension", "RadialDimension", "LevelDimension", "AngleDimension", "Text", "Label", "Zone",
    "Hatch", "Line", "PolyLine", "Arc", "Circle", "Spline", "Hotspot", "CutPlane", "Camera",
    "CamSet", "Group", "SectElem", "Drawing", "Picture", "Detail", "Elevation", "InteriorElevation",
    "Worksheet", "Hotlink", "CurtainWall", "CurtainWallSegment", "CurtainWallFrame",
    "CurtainWallPanel", "CurtainWallJunction", "CurtainWallAccessory", "Shell", "Skylight", "Morph",
    "ChangeMarker", "Stair", "Riser", "Tread", "StairStructure", "Railing", "RailingToprail",
    "RailingHandrail", "RailingRail", "RailingPost", "RailingInnerPost", "RailingBaluster",
    "RailingPanel", "RailingSegment", "RailingNode", "RailingBalusterSet", "RailingPattern",
    "RailingToprailEnd", "RailingHandrailEnd", "RailingRailEnd", "RailingToprailConnection",
    "RailingHandrailConnection", "RailingRailConnection", "RailingEndFinish", "BeamSegment",
    "ColumnSegment", "Opening",
]


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


@mcp.tool(
    name="jjp_export_localized_names",
    title="Export Archicad UI-language names",
    description=(
        "Reads the UI-language (e.g. Traditional Chinese) names Archicad uses for element types and for "
        "every built-in property and property group, and writes them as JSON to "
        "<JJP_STANDARDS_DIR>/archicad_localized_names.json (or output_path). Element type names are "
        "sampled from one existing element per type, so only types present in the project are covered. "
        "Returns a summary only. Read-only for the project."
    ),
    annotations=READ_ONLY,
)
def jjp_export_localized_names(port: int, output_path: str | None = None) -> dict:
    header = _get_header(port)
    core = header.core

    def prop_id(non_localized: str) -> dict | None:
        res = core.post_command("API.GetPropertyIds", {"properties": [{"type": "BuiltIn", "nonLocalizedName": non_localized}]})
        item = (res.get("properties") or [{}])[0]
        return item.get("propertyId")

    # 1. Element types: one sample element per type -> General_Type display value
    type_pid = prop_id("General_Type")
    samples, missing = {}, []
    for etype in _ELEMENT_TYPES:
        try:
            elems = core.post_command("API.GetElementsByType", {"elementType": etype}).get("elements", [])
        except Exception:  # type not supported by this Archicad version
            elems = []
        if elems:
            samples[etype] = elems[0]
        else:
            missing.append(etype)
    element_types = {}
    if type_pid and samples:
        names = list(samples)
        res = core.post_command(
            "API.GetPropertyValuesOfElements",
            {"elements": [samples[n] for n in names], "properties": [{"propertyId": type_pid}]},
        )
        for etype, item in zip(names, res.get("propertyValuesForElements", [])):
            values = item.get("propertyValues") or [{}]
            element_types[etype] = values[0].get("propertyValue", {}).get("value")

    # 2. Built-in properties: nonLocalizedName -> localized group / name
    all_names = core.post_command("API.GetAllPropertyNames", {}).get("properties", [])
    builtin = [p["nonLocalizedName"] for p in all_names if p.get("type") == "BuiltIn"]
    properties = {}
    for chunk in _chunks(builtin, 200):
        ids = core.post_command(
            "API.GetPropertyIds", {"properties": [{"type": "BuiltIn", "nonLocalizedName": n} for n in chunk]}
        ).get("properties", [])
        pairs = [(n, i["propertyId"]) for n, i in zip(chunk, ids) if "propertyId" in i]
        if not pairs:
            continue
        details = core.post_command(
            "API.GetDetailsOfProperties", {"properties": [{"propertyId": pid} for _, pid in pairs]}
        ).get("propertyDefinitions", [])
        for (n, _), d in zip(pairs, details):
            pd = d.get("propertyDefinition")
            if pd:
                properties[n] = {"group": pd.get("group", {}).get("name"), "name": pd.get("name"), "type": pd.get("type")}

    groups = sorted({v["group"] for v in properties.values() if v.get("group")})
    data = {
        "source": {"projectName": _project_name(header), "port": port, "tool": "jjp_export_localized_names"},
        "elementTypes": element_types,
        "elementTypesNotSampled": missing,
        "builtInPropertyGroups": groups,
        "builtInProperties": properties,
    }
    out = Path(output_path) if output_path else std.standards_dir() / "archicad_localized_names.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "written": str(out),
        "elementTypesSampled": len(element_types),
        "elementTypesNotSampled": missing,
        "builtInProperties": len(properties),
        "builtInPropertyGroups": len(groups),
        "elementTypes": element_types,
    }
