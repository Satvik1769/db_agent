#!/usr/bin/env python3
"""
CLI script: introspect the database and write/merge schema/metadata.yaml.

Usage:
    python scripts/introspect_db.py [--output schema/metadata.yaml] [--samples N] [--schema public]

Preserves existing human-authored description fields.
Adds new tables/columns discovered in the DB.
"""
import argparse
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from config.settings import settings
from db.connection import get_engine
from schema.introspector import introspect_schema, fetch_sample_rows


def load_existing_yaml(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return data
    return {}


def merge_into_yaml(existing: dict, introspected: dict, engine, n_samples: int, db_schema: str) -> dict:
    if "tables" not in existing:
        existing["tables"] = {}
    if "version" not in existing:
        existing["version"] = "1.0"
    if "database_description" not in existing:
        existing["database_description"] = ""

    for table_name, table_meta in introspected.items():
        if table_name not in existing["tables"]:
            existing["tables"][table_name] = {"description": "", "columns": {}}

        table_entry = existing["tables"][table_name]
        if "description" not in table_entry:
            table_entry["description"] = ""
        if "columns" not in table_entry:
            table_entry["columns"] = {}

        # Fetch sample rows
        samples = fetch_sample_rows(engine, table_name, n=n_samples, db_schema=db_schema)
        if samples:
            table_entry["sample_rows"] = samples

        for col in table_meta.columns:
            if col.name not in table_entry["columns"]:
                table_entry["columns"][col.name] = {}

            col_entry = table_entry["columns"][col.name]
            # Always update structural info from DB
            col_entry["type"] = col.type
            col_entry["nullable"] = col.nullable
            if col.is_pk:
                col_entry["pk"] = True
            if col.is_fk and col.fk_references:
                col_entry["fk"] = col.fk_references
            # Preserve or initialize human-authored fields
            if "description" not in col_entry:
                col_entry["description"] = ""
            if "units" not in col_entry:
                col_entry["units"] = None
            if "enum_values" not in col_entry:
                col_entry["enum_values"] = None

    return existing


def main():
    parser = argparse.ArgumentParser(description="Introspect DB and generate metadata.yaml")
    parser.add_argument("--output", default="schema/metadata.yaml", help="Output YAML path")
    parser.add_argument("--samples", type=int, default=3, help="Sample rows per table")
    parser.add_argument("--schema", default="public", help="PostgreSQL schema name")
    args = parser.parse_args()

    print(f"Connecting to database...")
    engine = get_engine()

    print(f"Introspecting schema '{args.schema}'...")
    introspected = introspect_schema(engine, db_schema=args.schema)
    print(f"Found {len(introspected)} tables: {', '.join(sorted(introspected.keys()))}")

    existing = load_existing_yaml(args.output)
    merged = merge_into_yaml(existing, introspected, engine, n_samples=args.samples, db_schema=args.schema)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w") as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=True, allow_unicode=True)

    print(f"\nWritten to {args.output}")
    print("Next: open the file and fill in 'description' fields for tables and columns.")


if __name__ == "__main__":
    main()
