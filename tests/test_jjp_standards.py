from pathlib import Path

from tapir_archicad_mcp.tools.custom import jjp_standards as std

SAMPLE = """# JJP Layer Naming Standards (DP-018A)

## Architecture (A-)
- `A-CLNG`: 天花版 / 天花物件
- `A-WALL-EX`: 外牆

## Green Building (G-)
- `G-GB-雨水`, `G-GB-保水`, `G-GB-綠化` 等
"""


def test_parse_layer_standards():
    layers = std.parse_layer_standards(SAMPLE)
    assert layers["A-CLNG"] == "天花版 / 天花物件"
    assert layers["A-WALL-EX"] == "外牆"
    assert {"G-GB-雨水", "G-GB-保水", "G-GB-綠化"} <= layers.keys()
    assert len(layers) == 5


def test_audit_layer_statuses():
    standards = std.parse_layer_standards(SAMPLE)
    assert std.audit_layer("A-CLNG", standards)[0] == "CONFORMING"
    assert std.audit_layer("A-CLNG-NEW", standards)[0] == "CUSTOM_VALID"
    assert std.audit_layer("牆", standards)[0] == "VIOLATION_PREFIX"
    assert std.audit_layer("ArchiCAD 圖層", standards)[0] == "SYSTEM_LAYER"


def test_audit_layers_counts():
    standards = std.parse_layer_standards(SAMPLE)
    result = std.audit_layers(
        [{"name": n} for n in ["A-CLNG", "A-X", "bad", "ArchiCAD Layer"]], standards
    )
    assert (result.conforming, result.custom, result.violations, result.system) == (1, 1, 1, 1)
    assert result.compliance_rate == 0.75


def test_property_groups():
    assert std.classify_property_group("<<JJP>> 基本")[0] == "JJP_CONFORMING"
    assert std.classify_property_group("<TAI> 法規")[0] == "JJP_CONFORMING"
    assert std.classify_property_group("JJP 資訊")[0] == "NON_STANDARD_JJP_GROUP"
    assert std.classify_property_group("一般")[0] == "OTHER_GROUP"


def test_real_standards_file_if_present():
    path = std.standards_dir() / "layer_standards.md"
    if Path(path).exists():
        layers = std.load_layer_standards(path)
        assert "A-CLNG" in layers and "S-GRID" in layers
