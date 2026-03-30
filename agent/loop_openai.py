import json
import time
from dataclasses import dataclass, field

import pandas as pd
from openai import OpenAI

from agent.loop import TurnResult, _format_df_for_llm
from agent.prompts import build_system_prompt, build_error_correction_message
from config.settings import settings
from db.executor import run_query

# OpenAI function definition (mirrors RUN_SQL_TOOL but in OpenAI's format)
RUN_SQL_FUNCTION = {
    "type": "function",
    "function": {
        "name": "run_sql",
        "description": (
            "Execute a read-only SQL SELECT query against the PostgreSQL database. "
            "Use this to retrieve data needed to answer the user's question. "
            "Only SELECT statements are allowed. CTEs (WITH ... AS ...) are supported."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of what this query fetches and why it answers the question.",
                },
                "sql": {
                    "type": "string",
                    "description": "The SQL SELECT query to execute.",
                },
            },
            "required": ["reasoning", "sql"],
        },
    },
}


def run_agent_turn_openai(
    question: str,
    conversation_history: list[dict],
    schema_context: str,
    client: OpenAI,
) -> TurnResult:
    start_time = time.time()
    result = TurnResult(question=question)

    system_prompt = build_system_prompt(schema_context)

    # OpenAI puts the system prompt inside the messages list
    messages = (
        [{"role": "system", "content": system_prompt}]
        + list(conversation_history)
        + [{"role": "user", "content": question}]
    )

    attempt = 0
    last_df: pd.DataFrame | None = None
    last_sql: str | None = None
    was_truncated = False

    while True:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            max_tokens=4096,
            tools=[RUN_SQL_FUNCTION],
            messages=messages,
        )

        choice = response.choices[0]
        message = choice.message

        # Track token usage
        result.token_usage = {
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
        }

        if choice.finish_reason == "stop":
            result.final_answer = message.content or ""
            break

        if choice.finish_reason == "tool_calls":
            tool_call = message.tool_calls[0]
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                result.error = "Failed to parse tool call arguments from model."
                break

            sql = args.get("sql", "")
            result.sql_attempts.append(sql)

            # Append the assistant message (with tool_calls) to history
            messages.append(message)

            # Execute the query
            query_result = run_query(sql)

            if query_result.error:
                attempt += 1
                if attempt >= settings.MAX_LLM_RETRIES:
                    result.error = f"Query failed after {settings.MAX_LLM_RETRIES} attempts. Last error: {query_result.error}"
                    # Send the error back so the model can give a graceful answer
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error: {query_result.error}",
                    })
                    final_response = client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        max_tokens=1024,
                        tools=[RUN_SQL_FUNCTION],
                        messages=messages,
                    )
                    result.final_answer = final_response.choices[0].message.content or ""
                    break

                # Inject error + correction hint, retry
                error_msg = build_error_correction_message(sql, query_result.error, attempt)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": f"Error: {query_result.error}\n\n{error_msg}",
                })
            else:
                last_df = query_result.df
                last_sql = sql
                was_truncated = query_result.was_truncated

                result_text = _format_df_for_llm(query_result.df, query_result.was_truncated)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text,
                })
        else:
            result.error = f"Unexpected finish reason: {choice.finish_reason}"
            break

    result.final_sql = last_sql
    result.result_df = last_df
    result.was_truncated = was_truncated
    result.duration_seconds = time.time() - start_time
    return result
