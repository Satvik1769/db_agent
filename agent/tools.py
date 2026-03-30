RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": (
        "Execute a read-only SQL SELECT query against the PostgreSQL database. "
        "Use this tool to retrieve data needed to answer the user's question. "
        "Only SELECT statements are allowed. CTEs (WITH ... AS ...) are supported. "
        "Results are returned as a table. Large result sets are automatically truncated to 10,000 rows."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": (
                    "Brief explanation of what this query fetches and why it answers the question. "
                    "Write this before the SQL."
                ),
            },
            "sql": {
                "type": "string",
                "description": "The SQL SELECT query to execute. Must be a valid PostgreSQL SELECT statement.",
            },
        },
        "required": ["reasoning", "sql"],
    },
}
