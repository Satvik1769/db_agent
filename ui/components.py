import pandas as pd
import streamlit as st


def render_connection_status(ok: bool, detail: str) -> None:
    if ok:
        st.sidebar.success(f"Connected\n\n{detail}")
    else:
        st.sidebar.error(f"Disconnected\n\n{detail}")


def render_sql_block(sql: str, attempt_number: int | None = None) -> None:
    label = "SQL Query"
    if attempt_number is not None and attempt_number > 1:
        label = f"SQL Query (attempt {attempt_number})"
    with st.expander(label, expanded=False):
        st.code(sql, language="sql")


def render_result_table(df: pd.DataFrame, was_truncated: bool) -> None:
    if df is None or df.empty:
        return
    row_count = len(df)
    if was_truncated:
        st.warning(f"Results limited to {row_count:,} rows. There may be more data.", icon="")
    else:
        st.caption(f"{row_count:,} row{'s' if row_count != 1 else ''} returned")
    st.dataframe(df, use_container_width=True)


def render_answer(text: str) -> None:
    st.markdown(text)


def render_error(error: str) -> None:
    st.error(f"**Could not complete query:** {error}", icon="")


def render_thinking_spinner():
    return st.spinner("Querying database...")
