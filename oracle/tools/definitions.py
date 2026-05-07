"""JSON schema definitions passed to Claude as the agent's tool list."""

TOOL_DEFINITIONS = [
    {
        "name": "search_artifacts",
        "description": (
            "Find data warehouse artifacts (tables, models, columns, DAGs) by natural-language "
            "description. Use this when the user asks about a concept (e.g. 'user purchases') "
            "and you don't know the exact artifact name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The natural language query."},
                "k": {"type": "integer", "description": "Max results.", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_lineage",
        "description": (
            "Walk the lineage graph up or down from a node. Use 'up' for 'what feeds X?' "
            "and 'down' for 'what depends on X?'. node_id is in the form 'model:foo' or "
            "'source:bar'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["up", "down"]},
                "depth": {"type": "integer", "default": 3},
            },
            "required": ["node_id", "direction"],
        },
    },
    {
        "name": "get_schema",
        "description": (
            "Return columns, types, and row count for a fully qualified table name "
            "(schema.table). Use when the user asks about table structure."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Fully qualified table name e.g. 'raw.users'.",
                }
            },
            "required": ["table"],
        },
    },
    {
        "name": "find_references",
        "description": (
            "Find all .sql and .py files where a column or table name appears, with "
            "file path and line number. Use this for impact analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "needle": {"type": "string", "description": "Column or table name to search for."}
            },
            "required": ["needle"],
        },
    },
]
