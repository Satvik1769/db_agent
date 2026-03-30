from dataclasses import dataclass, field

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass
class ColumnMeta:
    name: str
    type: str
    nullable: bool
    is_pk: bool
    is_fk: bool
    fk_references: str | None = None


@dataclass
class TableMeta:
    schema: str
    name: str
    columns: list[ColumnMeta] = field(default_factory=list)
    sample_rows: list[dict] = field(default_factory=list)


def introspect_schema(engine: Engine, db_schema: str = "public") -> dict[str, TableMeta]:
    inspector = inspect(engine)
    tables: dict[str, TableMeta] = {}

    table_names = inspector.get_table_names(schema=db_schema)

    for table_name in table_names:
        pk_cols = set(inspector.get_pk_constraint(table_name, schema=db_schema).get("constrained_columns", []))

        fk_map: dict[str, str] = {}
        for fk in inspector.get_foreign_keys(table_name, schema=db_schema):
            for local_col, ref_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                ref_table = fk["referred_table"]
                fk_map[local_col] = f"{ref_table}.{ref_col}"

        columns = []
        for col in inspector.get_columns(table_name, schema=db_schema):
            col_name = col["name"]
            columns.append(ColumnMeta(
                name=col_name,
                type=str(col["type"]),
                nullable=col.get("nullable", True),
                is_pk=col_name in pk_cols,
                is_fk=col_name in fk_map,
                fk_references=fk_map.get(col_name),
            ))

        tables[table_name] = TableMeta(
            schema=db_schema,
            name=table_name,
            columns=columns,
        )

    return tables


def fetch_sample_rows(engine: Engine, table: str, n: int = 3, db_schema: str = "public") -> list[dict]:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f'SELECT * FROM "{db_schema}"."{table}" LIMIT {n}'))
            columns = list(result.keys())
            rows = []
            for row in result.fetchall():
                row_dict = {}
                for col, val in zip(columns, row):
                    # Truncate long string values to avoid token bloat
                    str_val = str(val) if val is not None else "NULL"
                    row_dict[col] = str_val[:80] + "..." if len(str_val) > 80 else str_val
                rows.append(row_dict)
            return rows
    except Exception:
        return []
