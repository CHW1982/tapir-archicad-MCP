import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from tapir_archicad_mcp.app import mcp
from tapir_archicad_mcp.context import multi_conn_instance
from multiconn_archicad.basic_types import Port

log = logging.getLogger(__name__)

# --- Paths ---
WORKFLOW_CONFIG_PATH = Path("D:/20_Digital_Transformation/05_Workspace_Dev/Architect_CTO_Workflow.mcp.json")
SKILL_REF_PATH = Path("D:/20_Digital_Transformation/.gemini/skills/jjp-compliance-expert/references")

# --- DP-018A Standard Layers Mapping ---
STANDARD_LAYERS = {
    # Architecture
    "A-CLNG": "天花版 / 天花物件",
    "A-DIM": "一般標註 (高程 / 長度)",
    "A-DIM-LAW": "都審 / 執照標註",
    "A-DIM-CLNG": "天花圖一般標註",
    "A-FLOOR": "室內鋪面",
    "A-HIDE": "隱藏物件 (布林物件等)",
    "A-LABEL": "平面圖詳圖標記",
    "A-LABEL-HID": "平面隱藏詳圖標記",
    "A-LABEL-WALL": "牆面 Type 標記",
    "A-LAW": "法規檢討 2D 標記",
    "A-OBJE": "實體物件 (傢具等)",
    "A-OBJE-2D": "說明物件 (洩水方向等)",
    "A-OBJE-MEP": "機電物件",
    "A-RAIL": "扶手欄杆",
    "A-RAIL-HID": "隱藏扶手欄杆",
    "A-ROOF": "屋頂版",
    "A-STRS": "樓梯 / 手扶梯",
    "A-TEXT": "一般說明文字",
    "A-WALL-EX": "外牆",
    "A-WALL-IN": "室內隔間牆",
    "A-WALL-INT": "室裝裝飾板",
    "A-ZONE": "區域 / 區域圍封",
    
    # Structure
    "S-BEAM": "結構樑 / 桁架",
    "S-BEAM-SHOW": "平面圖顯示梁",
    "S-COL": "結構柱",
    "S-FNDN": "基礎版 / 地梁",
    "S-GRID": "柱軸線",
    "S-SLAB": "樓板",
    "S-WALL": "地下室覆土外牆",
    
    # Landscape
    "L-LNSP": "景觀鋪面 / 地形 / 道路",
    "L-SITE": "地界 / 建築線",
    
    # Green Building
    "G-GB-雨水": "綠建築雨水指標",
    "G-GB-保水": "綠建築保水指標",
    "G-GB-綠化": "綠建築綠化指標"
}

# Allowed Prefixes
ALLOWED_PREFIXES = ["A-", "S-", "L-", "G-"]

# --- Resources ---

@mcp.resource("jjp://workspace/workflow_config")
def get_workflow_config() -> str:
    """Reads and returns the content of the JJP Architect CTO workflow configuration JSON."""
    if not WORKFLOW_CONFIG_PATH.exists():
        return f"Error: Configuration file not found at {WORKFLOW_CONFIG_PATH}"
    
    try:
        content = WORKFLOW_CONFIG_PATH.read_text(encoding="utf-8")
        return content
    except Exception as e:
        return f"Error reading workflow config: {e}"


@mcp.resource("jjp://workspace/standards")
def get_jjp_standards() -> str:
    """Combines and returns layer and property standards documentation as a markdown resource."""
    standards_text = "# JJP Architects & Planners BIM Standards (DP-018A)\n\n"
    
    # Read Layer standards
    layer_file = SKILL_REF_PATH / "layer_standards.md"
    if layer_file.exists():
        standards_text += "## 📂 Layer Standards\n\n"
        standards_text += layer_file.read_text(encoding="utf-8")
        standards_text += "\n\n"
    else:
        standards_text += "## 📂 Layer Standards\nLayer standards reference not found.\n\n"
        
    # Read Property standards
    prop_file = SKILL_REF_PATH / "property_standards.md"
    if prop_file.exists():
        standards_text += "## 🏷️ Property Standards\n\n"
        standards_text += prop_file.read_text(encoding="utf-8")
        standards_text += "\n\n"
    else:
        standards_text += "## 🏷️ Property Standards\nProperty standards reference not found.\n\n"
        
    return standards_text


# --- Tools ---

@mcp.tool(
    name="jjp_get_transformation_config",
    title="Get JJP Transformation Config",
    description="Loads and parses the Architect_CTO_Workflow.mcp.json file, providing paths to goals, objectives, strategy, standards, and operational rules."
)
def jjp_get_transformation_config() -> dict:
    log.info("Executing jjp_get_transformation_config...")
    if not WORKFLOW_CONFIG_PATH.exists():
        return {"error": f"Configuration file not found at {WORKFLOW_CONFIG_PATH}"}
    
    try:
        with open(WORKFLOW_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Failed to parse workflow config: {e}")
        return {"error": f"Failed to parse workflow config: {e}"}


@mcp.tool(
    name="jjp_read_resource_path",
    title="Browse JJP Transformation Resources",
    description=(
        "Retrieves files and folders located under specific digital transformation resource directories. "
        "Allowed resource_name includes: 'PLAN_GOALS', 'PLAN_OBJECTIVES', 'PLAN_TEMPLATE', 'STRATEGY', 'STANDARDS', 'PROJECTS', 'TECH_R_D', 'INFRASTRUCTURE', 'KNOWLEDGE'."
    )
)
def jjp_read_resource_path(resource_name: str) -> dict:
    log.info(f"Executing jjp_read_resource_path for '{resource_name}'...")
    config = jjp_get_transformation_config()
    if "error" in config:
        return config
        
    definitions = config.get("definitions", {})
    if resource_name not in definitions:
        return {"error": f"Resource name '{resource_name}' not defined in workflow configuration."}
        
    rel_path = definitions[resource_name].get("path")
    description = definitions[resource_name].get("description")
    
    # Combine with workspace_root (normally D:/)
    workspace_root = config.get("workspace_root", "D:/")
    target_path = Path(workspace_root) / rel_path
    
    if not target_path.exists():
        # Try checking absolute path direct if rel_path is already absolute
        target_path = Path(rel_path)
        if not target_path.exists():
            return {
                "resource_name": resource_name,
                "description": description,
                "configured_path": str(rel_path),
                "resolved_absolute_path": str(target_path),
                "status": "NOT_FOUND",
                "error": "The specified path does not exist on disk."
            }
            
    # List contents
    try:
        items = []
        for child in target_path.iterdir():
            items.append({
                "name": child.name,
                "is_directory": child.is_dir(),
                "size_bytes": child.stat().st_size if child.is_file() else None
            })
        return {
            "resource_name": resource_name,
            "description": description,
            "resolved_absolute_path": str(target_path.resolve()),
            "status": "FOUND",
            "items": items
        }
    except Exception as e:
        return {
            "resource_name": resource_name,
            "resolved_absolute_path": str(target_path.resolve()),
            "status": "ERROR",
            "error": f"Failed to list directory contents: {e}"
        }


@mcp.tool(
    name="jjp_audit_layers",
    title="JJP BIM Layer Audit (DP-018A)",
    description="Audits layers of an active Archicad instance against JJP BIM Standard DP-018A. Ensures layers use correct prefixes and match standard names."
)
def jjp_audit_layers(port: int) -> dict:
    log.info(f"Executing jjp_audit_layers on port {port}...")
    try:
        multi_conn = multi_conn_instance.get()
    except LookupError:
        return {"status": "ERROR", "error": "Server error: could not access MultiConn instance."}
        
    target_port = Port(port)
    if target_port not in multi_conn.active:
        return {"status": "ERROR", "error": f"Port {port} is not an active Archicad connection."}
        
    conn_header = multi_conn.active[target_port]
    
    try:
        # 1. Get Layer Attribute IDs
        log.info("Fetching Layer Attribute IDs from Archicad...")
        ids_response = conn_header.core.post_command(
            command="API.GetAttributesByType",
            parameters={"attributeType": "Layer"}
        )
        
        attribute_ids = ids_response.get("attributeIds", [])
        if not attribute_ids:
            return {
                "port": port,
                "projectName": conn_header.archicad_id.projectName,
                "status": "SUCCESS",
                "summary": "No layers found in the project.",
                "layerCount": 0,
                "conformingCount": 0,
                "customCount": 0,
                "violationCount": 0,
                "details": []
            }
            
        # 2. Get Layer Attributes details
        log.info(f"Fetching details for {len(attribute_ids)} layers...")
        details_response = conn_header.core.post_command(
            command="API.GetLayerAttributes",
            parameters={"attributeIds": attribute_ids}
        )
        
        attributes = details_response.get("attributes", [])
        
        # 3. Audit layers
        report_details = []
        conforming_count = 0
        custom_count = 0
        violation_count = 0
        
        for attr_item in attributes:
            # Parse layer data safely
            layer_attr = attr_item.get("layerAttribute")
            if not layer_attr:
                continue
                
            guid = layer_attr.get("attributeId", {}).get("guid")
            name = layer_attr.get("name", "")
            is_locked = layer_attr.get("isLocked", False)
            is_hidden = layer_attr.get("isHidden", False)
            
            # Skip built-in Archicad system layer (typically index 1, named "ArchiCAD Layer" or "ArchiCAD 圖層")
            if "archicad" in name.lower():
                report_details.append({
                    "name": name,
                    "guid": guid,
                    "status": "SYSTEM_LAYER",
                    "description": "Built-in ArchiCAD system layer",
                    "isLocked": is_locked,
                    "isHidden": is_hidden
                })
                conforming_count += 1
                continue
                
            # Check Prefix conformity
            has_valid_prefix = any(name.startswith(pfx) for pfx in ALLOWED_PREFIXES)
            
            if not has_valid_prefix:
                violation_count += 1
                report_details.append({
                    "name": name,
                    "guid": guid,
                    "status": "VIOLATION_PREFIX",
                    "description": f"Violates JJP prefix convention. Must start with one of: {ALLOWED_PREFIXES}",
                    "isLocked": is_locked,
                    "isHidden": is_hidden
                })
            else:
                # Check standard layer matching
                if name in STANDARD_LAYERS:
                    conforming_count += 1
                    report_details.append({
                        "name": name,
                        "guid": guid,
                        "status": "CONFORMING",
                        "description": STANDARD_LAYERS[name],
                        "isLocked": is_locked,
                        "isHidden": is_hidden
                    })
                else:
                    custom_count += 1
                    # It has a standard prefix but is a custom sub-layer (allowed under DP-018A but noted)
                    report_details.append({
                        "name": name,
                        "guid": guid,
                        "status": "CUSTOM_VALID",
                        "description": "Custom layer with standard JJP prefix. Standard compliant.",
                        "isLocked": is_locked,
                        "isHidden": is_hidden
                    })
                    
        total_layers = len(report_details)
        compliance_rate = (conforming_count + custom_count) / total_layers if total_layers > 0 else 1.0
        
        return {
            "port": port,
            "projectName": conn_header.archicad_id.projectName,
            "status": "SUCCESS",
            "layerCount": total_layers,
            "conformingCount": conforming_count,
            "customCount": custom_count,
            "violationCount": violation_count,
            "complianceRate": f"{compliance_rate:.1%}",
            "summary": (
                f"Audited {total_layers} layers. Conforming standard: {conforming_count}, "
                f"Conforming custom: {custom_count}, Violations: {violation_count}. "
                f"Overall compliance rate is {compliance_rate:.1%}."
            ),
            "details": report_details
        }
        
    except Exception as e:
        log.error(f"Error auditing layers: {e}")
        return {"status": "ERROR", "error": f"Failed to audit layers: {e}"}


@mcp.tool(
    name="jjp_audit_properties",
    title="JJP BIM Property Group Audit",
    description="Audits property definitions of an active Archicad instance to ensure JJP specific property groups start with standard prefixes <<JJP>>, <TAI>, or <AC>."
)
def jjp_audit_properties(port: int) -> dict:
    log.info(f"Executing jjp_audit_properties on port {port}...")
    try:
        multi_conn = multi_conn_instance.get()
    except LookupError:
        return {"status": "ERROR", "error": "Server error: could not access MultiConn instance."}
        
    target_port = Port(port)
    if target_port not in multi_conn.active:
        return {"status": "ERROR", "error": f"Port {port} is not an active Archicad connection."}
        
    conn_header = multi_conn.active[target_port]
    
    try:
        # 1. Fetch all property IDs
        log.info("Fetching all Property IDs from Archicad...")
        ids_response = conn_header.core.post_command(
            command="API.GetAllPropertyIds",
            parameters={"propertyType": "UserDefined"}
        )
        
        properties_list = ids_response.get("properties", [])
        if not properties_list:
            return {
                "port": port,
                "projectName": conn_header.archicad_id.projectName,
                "status": "SUCCESS",
                "summary": "No user-defined property definitions found in the project.",
                "totalProperties": 0,
                "jjpConforming": 0,
                "misplacedOrNonStandardJjp": 0,
                "otherGroups": 0,
                "details": []
            }
            
        # 2. Get detailed definitions
        log.info(f"Fetching details for {len(properties_list)} properties...")
        details_response = conn_header.core.post_command(
            command="API.GetDetailsOfProperties",
            parameters={"properties": properties_list}
        )
        
        definitions = details_response.get("propertyDefinitions", [])
        
        # JJP Property Standard Groups
        jjp_prefixes = ["<<JJP>>", "<TAI>", "<AC>"]
        
        report_details = []
        jjp_conforming = 0
        misplaced_non_standard = 0
        other_groups = 0
        
        for item in definitions:
            prop_def = item.get("propertyDefinition")
            if not prop_def:
                continue
                
            property_id = prop_def.get("propertyId", {}).get("guid")
            name = prop_def.get("name", "")
            group_obj = prop_def.get("group", {})
            group_name = group_obj.get("name", "")
            group_guid = group_obj.get("propertyGroupId", {}).get("guid")
            prop_type = prop_def.get("type", "")
            
            # Check Group Name
            is_jjp_group = any(group_name.startswith(pfx) for pfx in jjp_prefixes)
            contains_jjp_or_tai = "jjp" in group_name.lower() or "tai" in group_name.lower()
            
            if is_jjp_group:
                jjp_conforming += 1
                report_details.append({
                    "name": name,
                    "guid": property_id,
                    "group": group_name,
                    "groupGuid": group_guid,
                    "type": prop_type,
                    "status": "JJP_CONFORMING",
                    "description": "Standard JJP property group"
                })
            elif contains_jjp_or_tai:
                misplaced_non_standard += 1
                report_details.append({
                    "name": name,
                    "guid": property_id,
                    "group": group_name,
                    "groupGuid": group_guid,
                    "type": prop_type,
                    "status": "NON_STANDARD_JJP_GROUP",
                    "description": "Group name contains JJP or TAI but lacks proper prefix format (e.g. <<JJP>> or <TAI>)."
                })
            else:
                other_groups += 1
                report_details.append({
                    "name": name,
                    "guid": property_id,
                    "group": group_name,
                    "groupGuid": group_guid,
                    "type": prop_type,
                    "status": "OTHER_GROUP",
                    "description": "Standard built-in or other generic property group"
                })
                
        total_properties = len(report_details)
        
        return {
            "port": port,
            "projectName": conn_header.archicad_id.projectName,
            "status": "SUCCESS",
            "totalProperties": total_properties,
            "jjpConforming": jjp_conforming,
            "misplacedOrNonStandardJjp": misplaced_non_standard,
            "otherGroups": other_groups,
            "summary": (
                f"Audited {total_properties} properties. Conforming JJP groups: {jjp_conforming}, "
                f"Non-standard JJP groups (warnings): {misplaced_non_standard}, Generic/Other groups: {other_groups}."
            ),
            "details": report_details
        }
        
    except Exception as e:
        log.error(f"Error auditing properties: {e}")
        return {"status": "ERROR", "error": f"Failed to audit properties: {e}"}
