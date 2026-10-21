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


def test_suffix_variants():
    standards = std.parse_layer_standards(SAMPLE)
    assert std.base_layer_name("A-CLNG.3D") == "A-CLNG"
    assert std.base_layer_name("A-WALL-EX(外)") == "A-WALL-EX"
    assert std.audit_layer("A-CLNG.3D", standards)[0] == "CONFORMING_VARIANT"
    assert std.audit_layer("G-GB-雨水.綠標章", standards)[0] == "CONFORMING_VARIANT"
    assert std.audit_layer("A-CLNG-X.3D", standards)[0] == "CUSTOM_VALID"


V2_LAYERS = """# x
## 允許前綴
- `A-`: 建築
- `E-`: 機電
## 後綴慣例
| `.2D` | 2D |
## Architecture (A-)
- `A-CLNG`: 天花版
## 待確認
| `T-Decoration` | ? |
"""

V2_PROPS = """# x
## JJP 群組前綴
- `<<JJP>>`: a
- `<LEBR>`: b
## 外部標準群組前綴
- `COBie 2:`: c
- `LCA `: d
## 群組命名慣例
| `(勿改)` | x |
## 主要屬性欄位
- `ID和類別`: y
"""


def test_v2_layer_prefixes_and_layers():
    assert std.parse_allowed_layer_prefixes(V2_LAYERS) == ("A-", "E-")
    assert std.parse_layer_standards(V2_LAYERS) == {"A-CLNG": "天花版"}
    prefixes = std.parse_allowed_layer_prefixes(V2_LAYERS)
    assert std.audit_layer("E-ELEC", {}, prefixes)[0] == "CUSTOM_VALID"
    assert std.audit_layer("T-Decoration", {}, prefixes)[0] == "VIOLATION_PREFIX"


def test_v1_file_falls_back_to_default_prefixes():
    assert std.parse_allowed_layer_prefixes(SAMPLE) == std.ALLOWED_LAYER_PREFIXES


def test_v2_property_prefixes():
    jjp, ext = std.parse_property_prefixes(V2_PROPS)
    assert jjp == ("<<JJP>>", "<LEBR>") and ext == ("COBie 2:", "LCA ")
    assert std.classify_property_group("<LEBR>金屬(材料)", jjp, ext)[0] == "JJP_CONFORMING"
    assert std.classify_property_group("COBie 2: Type", jjp, ext)[0] == "EXTERNAL_STANDARD"
    assert std.classify_property_group("LCA Doors", jjp, ext)[0] == "EXTERNAL_STANDARD"
    assert std.classify_property_group("Pset_Wall", jjp, ext)[0] == "OTHER_GROUP"
