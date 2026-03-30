import os

import anthropic
import streamlit as st

from agent.loop import run_agent_turn
from config.settings import settings
from db.connection import test_connection
from logging_.logger import log_turn
from schema.catalog import load_full_catalog, build_schema_context
from schema.selector import select_relevant_tables
from ui.components import (
    render_connection_status,
    render_sql_block,
    render_result_table,
    render_answer,
    render_error,
)


def _check_setup() -> list[str]:
    issues = []
    if not settings.DB_URL:
        issues.append("DB_URL is not set in .env")
    if not settings.ANTHROPIC_API_KEY:
        issues.append("ANTHROPIC_API_KEY is not set in .env")
    return issues


def _init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []  # Display history
    if "agent_history" not in st.session_state:
        st.session_state.agent_history = []  # Raw Anthropic messages list
    if "db_ok" not in st.session_state:
        st.session_state.db_ok = False
    if "db_detail" not in st.session_state:
        st.session_state.db_detail = "Not connected"
    if "schema_cache" not in st.session_state:
        st.session_state.schema_cache = None
    if "client" not in st.session_state:
        st.session_state.client = None


def _load_schema() -> None:
    if st.session_state.schema_cache is None and st.session_state.db_ok:
        with st.spinner("Loading schema..."):
            try:
                st.session_state.schema_cache = load_full_catalog()
            except Exception as e:
                st.warning(f"Could not load schema: {e}")
                st.session_state.schema_cache = {}


def main() -> None:
    st.set_page_config(
        page_title="DB Agent",
        page_icon="",
        layout="wide",
    )

    _init_session_state()

    # --- Sidebar ---
    with st.sidebar:
        st.title("DB Agent")
        st.caption("AI-powered database Q&A")
        st.divider()

        # Connection status (check once per session or on reconnect)
        if st.button("Test Connection", use_container_width=True):
            ok, detail = test_connection()
            st.session_state.db_ok = ok
            st.session_state.db_detail = detail
            if ok:
                st.session_state.schema_cache = None  # Force reload

        render_connection_status(st.session_state.db_ok, st.session_state.db_detail)

        st.divider()

        # Schema info
        if st.session_state.schema_cache:
            table_count = len(st.session_state.schema_cache)
            st.caption(f"{table_count} table{'s' if table_count != 1 else ''} loaded")

        # Clear conversation
        if st.button("Clear Conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.agent_history = []
            st.rerun()

        st.divider()
        st.caption(f"Model: {settings.CLAUDE_MODEL}")

    # --- Setup check ---
    setup_issues = _check_setup()
    if setup_issues:
        st.error("**Setup required before using DB Agent:**")
        for issue in setup_issues:
            st.write(f"- {issue}")
        st.info("Copy `.env.example` to `.env` and fill in your credentials.")
        return

    # --- Init client ---
    if st.session_state.client is None:
        st.session_state.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # --- Auto-connect on first load ---
    if not st.session_state.db_ok:
        ok, detail = test_connection()
        st.session_state.db_ok = ok
        st.session_state.db_detail = detail

    # --- Load schema ---
    _load_schema()

    # --- Main chat area ---
    st.title("Ask your database")

    if not st.session_state.messages:
        st.info(
            "Ask any question about your data in plain English. "
            "For example: *How many orders were placed last month?* or *Who are the top 10 customers by revenue?*"
        )

    # Render conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                if msg.get("sql_attempts"):
                    for i, sql in enumerate(msg["sql_attempts"], 1):
                        render_sql_block(sql, attempt_number=i if len(msg["sql_attempts"]) > 1 else None)
                if msg.get("result_df") is not None:
                    render_result_table(msg["result_df"], msg.get("was_truncated", False))
                if msg.get("error"):
                    render_error(msg["error"])
                if msg.get("answer"):
                    render_answer(msg["answer"])
            else:
                st.write(msg["content"])

    # Chat input
    if not st.session_state.db_ok:
        st.warning("Not connected to database. Click 'Test Connection' in the sidebar.")
        return

    question = st.chat_input("Ask a question about your data...")
    if not question:
        return

    # Display user message
    with st.chat_message("user"):
        st.write(question)
    st.session_state.messages.append({"role": "user", "content": question})

    # Get relevant schema context for this question
    schema_cache = st.session_state.schema_cache or {}
    relevant_tables = select_relevant_tables(question, schema_cache)
    schema_context = build_schema_context(relevant_tables) if relevant_tables else "No schema available."

    # Run agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            turn_result = run_agent_turn(
                question=question,
                conversation_history=st.session_state.agent_history,
                schema_context=schema_context,
                client=st.session_state.client,
            )

        # Render response
        if turn_result.sql_attempts:
            for i, sql in enumerate(turn_result.sql_attempts, 1):
                render_sql_block(sql, attempt_number=i if len(turn_result.sql_attempts) > 1 else None)

        if turn_result.result_df is not None and not turn_result.result_df.empty:
            render_result_table(turn_result.result_df, turn_result.was_truncated)

        if turn_result.error and not turn_result.final_answer:
            render_error(turn_result.error)

        if turn_result.final_answer:
            render_answer(turn_result.final_answer)

    # Update session state
    st.session_state.messages.append({
        "role": "assistant",
        "sql_attempts": turn_result.sql_attempts,
        "result_df": turn_result.result_df,
        "was_truncated": turn_result.was_truncated,
        "error": turn_result.error,
        "answer": turn_result.final_answer,
    })

    # Update raw Anthropic history for multi-turn context
    st.session_state.agent_history.append({"role": "user", "content": question})
    if turn_result.final_answer:
        st.session_state.agent_history.append({
            "role": "assistant",
            "content": turn_result.final_answer,
        })

    # Log the turn
    try:
        log_turn(turn_result)
    except Exception:
        pass  # Never let logging break the UI
