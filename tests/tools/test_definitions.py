from oracle.tools.definitions import TOOL_DEFINITIONS


def test_tool_definitions_has_four_tools():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"search_artifacts", "get_lineage", "get_schema", "find_references"}


def test_each_tool_has_input_schema():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
