import os
from dataclasses import dataclass, field

import yaml

from schema.introspector import TableMeta, ColumnMeta, introspect_schema


@dataclass
class EnrichedColumn:
    name: str
    type: str
    nullable: bool
    is_pk: bool
    is_fk: bool
    fk_references: str | None
    description: str = ""
    units: str | None = None
    enum_values: list | None = None


@dataclass
class EnrichedTable:
    schema: str
    name: str
    description: str = ""
    columns: list[EnrichedColumn] = field(default_factory=list)
    sample_rows: list[dict] = field(default_factory=list)


def load_yaml_catalog(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def merge_catalog(
    introspected: dict[str, TableMeta],
    yaml_catalog: dict,
) -> dict[str, EnrichedTable]:
    yaml_tables = yaml_catalog.get("tables", {})
    result: dict[str, EnrichedTable] = {}

    for table_name, table_meta in introspected.items():
        yaml_table = yaml_tables.get(table_name, {})
        yaml_cols = yaml_table.get("columns", {})
        sample_rows = yaml_table.get("sample_rows", [])

        enriched_cols = []
        for col in table_meta.columns:
            yaml_col = yaml_cols.get(col.name, {})
            enriched_cols.append(EnrichedColumn(
                name=col.name,
                type=col.type,
                nullable=col.nullable,
                is_pk=col.is_pk,
                is_fk=col.is_fk,
                fk_references=col.fk_references,
                description=yaml_col.get("description", ""),
                units=yaml_col.get("units"),
                enum_values=yaml_col.get("enum_values"),
            ))

        result[table_name] = EnrichedTable(
            schema=table_meta.schema,
            name=table_name,
            description=yaml_table.get("description", ""),
            columns=enriched_cols,
            sample_rows=sample_rows,
        )

    return result


def build_schema_context(tables: dict[str, EnrichedTable], include_samples: bool = True) -> str:
    if not tables:
        return "No schema information available."

    parts = []
    for table_name, table in tables.items():
        header = f"## Table: {table.schema}.{table_name}"
        if table.description:
            header += f"\n{table.description}"
        parts.append(header)

        # Column table
        col_lines = ["| Column | Type | Nullable | Notes |", "|--------|------|----------|-------|"]
        for col in table.columns:
            notes = []
            if col.is_pk:
                notes.append("PRIMARY KEY")
            if col.is_fk and col.fk_references:
                notes.append(f"FK → {col.fk_references}")
            if col.description:
                notes.append(col.description)
            if col.units:
                notes.append(f"units: {col.units}")
            if col.enum_values:
                notes.append(f"values: {', '.join(str(v) for v in col.enum_values)}")
            nullable_str = "YES" if col.nullable else "NO"
            col_lines.append(f"| {col.name} | {col.type} | {nullable_str} | {'; '.join(notes)} |")

        parts.append("\n".join(col_lines))

        # Sample rows
        if include_samples and table.sample_rows:
            parts.append(f"**Sample rows ({len(table.sample_rows)}):**")
            if table.sample_rows:
                headers = list(table.sample_rows[0].keys())
                sample_lines = ["| " + " | ".join(headers) + " |",
                                 "| " + " | ".join(["---"] * len(headers)) + " |"]
                for row in table.sample_rows:
                    sample_lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
                parts.append("\n".join(sample_lines))

        parts.append("")  # blank line between tables

    return "\n".join(parts)


def load_full_catalog(
    yaml_path: str = "schema/metadata.yaml",
    db_schema: str = "public",
) -> dict[str, EnrichedTable]:
    from db.connection import get_engine
    engine = get_engine()
    introspected = introspect_schema(engine, db_schema=db_schema)
    yaml_catalog = load_yaml_catalog(yaml_path)
    return merge_catalog(introspected, yaml_catalog)
