import argparse
import json
import os
import sys
from typing import Any, final, override

from powerbi_auth import get_access_token
from powerbi_client import PowerBIClient
from toolkit import Toolkit, serialize_tool_result

DEFAULT_DATASET_ID = "7ff60759-744c-4d52-a142-45b118676e43"
MAX_RESULT_ROWS = 100


def quote_identifier(name: str) -> str:
    """Quote a DAX table/column identifier if it isn't already quoted."""
    name = name.strip()
    if name.startswith(("'", "[")):
        return name
    return f"'{name}'"


def cap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hard-cap the number of rows so one DAX query can't blow up the context."""
    if len(rows) <= MAX_RESULT_ROWS:
        return rows
    omitted = len(rows) - MAX_RESULT_ROWS
    return rows[:MAX_RESULT_ROWS] + [{"__truncated__": f"{omitted} more rows omitted"}]


@final
class PowerBITools(Toolkit):
    """Tools for querying Power BI leasing datasets."""

    def __init__(self, client: PowerBIClient, dataset_id: str = ""):
        self.client = client
        self.dataset_id = dataset_id or os.getenv("DATASET_ID", DEFAULT_DATASET_ID)
        self._schema: dict[str, list[dict[str, str]]] = {}
        self._load_schema()

    def _load_schema(self) -> None:
        schema_path = os.path.join(os.path.dirname(__file__), "powerbi_schema.json")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                self._schema = json.load(f)

    @override
    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_powerbi_schema",
                "description": "List the tables available in the Power BI dataset (names + column counts). Call this first to discover tables.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_table_schema",
                "description": "Show the columns (name + type) of one Power BI table.",
                "input_schema": {
                    "type": "object",
                    "properties": {"table": {"type": "string"}},
                    "required": ["table"],
                },
            },
            {
                "name": "run_dax_query",
                "description": "Run a DAX query against the Power BI dataset. Always aggregate (SUMMARIZECOLUMNS) or use TOPN; full-table results are capped.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "dax_query": {
                            "type": "string",
                            "description": "The DAX query to execute (e.g., \"EVALUATE TOPN(10, 'TableName')\")",
                        }
                    },
                    "required": ["dax_query"],
                },
            },
        ]

    @override
    def execute(self, name: str, args: dict[str, Any]) -> str:
        """Route the tool name to the local python method and cap the output size."""
        if name == "get_powerbi_schema":
            res = self.list_tables()
        elif name == "get_table_schema":
            res = self.get_schema_str(str(args.get("table") or ""))
        elif name == "run_dax_query":
            res = self.run_dax(str(args.get("dax_query") or ""))
        else:
            raise ValueError(f"Unknown PowerBI tool: {name}")
            
        return serialize_tool_result(res)

    def list_tables(self) -> list[dict[str, object]]:
        """Return table names with column counts (cheap — call this first)."""
        return [
            {"table": name, "columns": len(cols)}
            for name, cols in self._schema.items()
        ]

    def get_schema_str(self, table: str = "") -> str:
        """Return the schema: one table, or a compact all-tables overview."""
        if not self._schema:
            return "Schema not loaded."
        if table:
            cols = self._schema.get(table)
            if cols is None:
                return f"Table '{table}' not found. Use get_powerbi_schema to see names."
            return f"Table: {table}\nColumns: " + ", ".join(
                f"{c['name']} ({c['type']})" for c in cols
            )
        lines = []
        for name, cols in self._schema.items():
            lines.append(f"{name}: " + ", ".join(c["name"] for c in cols))
        return "\n".join(lines)

    def run_dax(self, dax_query: str) -> list[dict[str, Any]]:
        """Execute a raw DAX query against the configured dataset (capped)."""
        return cap_rows(self.client.run_dax(self.dataset_id, dax_query))

    def preview_table(self, table: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return up to `limit` sample rows from a table (for CLI preview)."""
        if table not in self._schema:
            raise ValueError(
                f"Table '{table}' not found. Available: {', '.join(self._schema)}"
            )
        query = f"EVALUATE TOPN({int(limit)}, {quote_identifier(table)})"
        return cap_rows(self.client.run_dax(self.dataset_id, query))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="powerbi_tools",
        description="Inspect the Power BI leasing dataset (schema + data).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    _ = sub.add_parser("tables", help="List tables with column counts")

    schema_p = sub.add_parser("schema", help="Show schema (optionally one table)")
    _ = schema_p.add_argument("table", nargs="?", default="")

    preview_p = sub.add_parser("preview", help="Show sample rows from a table")
    _ = preview_p.add_argument("table")
    _ = preview_p.add_argument("--limit", type=int, default=20)

    dax_p = sub.add_parser("dax", help="Run a raw DAX query")
    _ = dax_p.add_argument("query")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    tools = PowerBITools(PowerBIClient(get_access_token()))

    if args.command == "tables":
        for row in tools.list_tables():
            print(f"{row['table']}  ({row['columns']} columns)")
    elif args.command == "schema":
        print(tools.get_schema_str(args.table))
    elif args.command == "preview":
        rows = tools.preview_table(args.table, args.limit)
        if not rows:
            print(f"Table '{args.table}' returned no rows.")
            return
        print(f"=== {args.table} (first {len(rows)} rows) ===")
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, default=str))
    elif args.command == "dax":
        for row in tools.run_dax(args.query):
            print(json.dumps(row, ensure_ascii=False, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - CLI should print a readable error
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
