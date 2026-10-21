from tapir_archicad_mcp.tools.custom import jjp_hotlinks as hl

TW = ("teamwork://%E5%AE%B6:eyJhbGciOiJSUzI1NiJ9%2Eabc.def@http%253A%252F%252F192%252E168%252E100%252E61%253A22001%252F"
      "/4%25E5%2595%2586%25E8%25BE%25A6%252FY15(Office)")


def test_mask_location_removes_token_and_decodes():
    masked = hl.mask_location(TW)
    assert "eyJ" not in masked and "%" not in masked
    assert masked == "teamwork://http://192.168.100.61:22001//4商辦/Y15(Office)"


def test_classify_location():
    pre = ["T:\\", "\\\\"]
    assert hl.classify_location(TW, pre) == "BIMCLOUD"
    assert hl.classify_location(r"T:\3710090\a.pln", pre) == "NETWORK_FILE"
    assert hl.classify_location(r"\\nas\bim\a.mod", pre) == "NETWORK_FILE"
    assert hl.classify_location(r"C:\Users\x\Desktop\a.pln", pre) == "LOCAL_FILE"
    assert hl.classify_location(r"D:\work\a.pln", pre) == "LOCAL_FILE"


def test_summarise_nodes_groups_and_flags():
    tree = [
        {"location": TW, "hotlinkNodeId": {"guid": "1"}, "name": "a"},
        {"location": TW, "hotlinkNodeId": {"guid": "2"}, "name": "b"},
        {"location": r"C:\Users\x\Desktop\a.pln", "hotlinkNodeId": {"guid": "3"},
         "children": [{"location": r"T:\b.mod"}]},
    ]
    s = hl.summarise_nodes(tree, ["T:\\"])
    office = s[hl.mask_location(TW)]
    assert len(office.nodes) == 2 and office.status(1) == ["REVIEW_MULTIPLE_NODES"]
    local = s[r"C:\Users\x\Desktop\a.pln"]
    assert local.status(1) == ["VIOLATION_LOCAL_PATH", "VIOLATION_NESTED"]


def test_params_and_instances():
    md = "## 稽核參數\n- `linkLayerPrefix`: A-LINK-\n- `maxNodesPerSource`: 2\n- `requireLockedLinkLayer`: false\n- `networkFilePrefixes`: T:\\, \\\\\n"
    p = hl.parse_params(md)
    assert p["maxNodesPerSource"] == 2 and p["requireLockedLinkLayer"] is False
    assert p["networkFilePrefixes"] == ["T:\\", "\\\\"]
    r = hl.audit_instance_layers(["A-LINK-a", "A-LINK-a", "A-WALL"], {"A-LINK-a": False}, "A-LINK-", True)
    assert r["instancesNotOnLinkLayer"] == 1 and r["unlockedLinkLayers"] == ["A-LINK-a"]
