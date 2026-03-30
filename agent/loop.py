import time
from dataclasses import dataclass, field

import anthropic
import pandas as pd

from agent.prompts import build_system_prompt, build_error_correction_message
from agent.tools import RUN_SQL_TOOL
from config.settings import settings
from db.executor import run_query


@dataclass
class TurnResult:
    question: str
    final_answer: str = ""
    sql_attempts: list[str] = field(default_factory=list)
    final_sql: str | None = None
    result_df: pd.DataFrame | None = None
    error: str | None = None
    was_truncated: bool = False
    duration_seconds: float = 0.0
    token_usage: dict = field(default_factory=dict)


def run_agent_turn(
    question: str,
    conversation_history: list[dict],
    schema_context: str,
    client: anthropic.Anthropic,
) -> TurnResult:
    start_time = time.time()
    result = TurnResult(question=question)

    system_prompt = build_system_prompt(schema_context)

    # Build initial messages: history + new user question
    messages = list(conversation_history) + [{"role": "user", "content": question}]

    attempt = 0
    last_df: pd.DataFrame | None = None
    last_sql: str | None = None
    was_truncated = False

    while True:
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=system_prompt,
            tools=[RUN_SQL_TOOL],
            messages=messages,
        )

        # Track token usage
        result.token_usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }

        if response.stop_reason == "end_turn":
            # Extract final text answer
            for block in response.content:
                if hasattr(block, "text"):
                    result.final_answer = block.text
                    break
            break

        if response.stop_reason == "tool_use":
            # Find the tool use block
            tool_use_block = None
            for block in response.content:
                if block.type == "tool_use":
                    tool_use_block = block
                    break

            if tool_use_block is None:
                result.error = "Model indicated tool_use but no tool_use block found."
                break

            sql = tool_use_block.input.get("sql", "")
            result.sql_attempts.append(sql)

            # Append assistant message with tool use
            messages.append({"role": "assistant", "content": response.content})

            # Execute the query
            query_result = run_query(sql)

            if query_result.error:
                attempt += 1
                if attempt >= settings.MAX_LLM_RETRIES:
                    result.error = f"Query failed after {settings.MAX_LLM_RETRIES} attempts. Last error: {query_result.error}"
                    # Append a final tool result so the model can give a graceful answer
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": f"Error: {query_result.error}",
                            "is_error": True,
                        }],
                    })
                    # One more turn to get a graceful failure answer
                    final_response = client.messages.create(
                        model=settings.CLAUDE_MODEL,
                        max_tokens=1024,
                        system=system_prompt,
                        tools=[RUN_SQL_TOOL],
                        messages=messages,
                    )
                    for block in final_response.content:
                        if hasattr(block, "text"):
                            result.final_answer = block.text
                            break
                    break

                # Inject error correction and retry
                error_msg = build_error_correction_message(sql, query_result.error, attempt)
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use_block.id,
                            "content": f"Error: {query_result.error}",
                            "is_error": True,
                        },
                        {
                            "type": "text",
                            "text": error_msg,
                        },
                    ],
                })
            else:
                # Success — format result as text for the model
                last_df = query_result.df
                last_sql = sql
                was_truncated = query_result.was_truncated

                result_text = _format_df_for_llm(query_result.df, query_result.was_truncated)
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": result_text,
                    }],
                })
        else:
            # Unexpected stop reason
            result.error = f"Unexpected stop reason: {response.stop_reason}"
            break

    result.final_sql = last_sql
    result.result_df = last_df
    result.was_truncated = was_truncated
    result.duration_seconds = time.time() - start_time
    return result


def _format_df_for_llm(df: pd.DataFrame, was_truncated: bool) -> str:
    if df.empty:
        return "Query returned 0 rows."

    row_count = len(df)
    truncation_note = f" (truncated to {row_count} rows — there may be more)" if was_truncated else ""

    # For small results, include all rows
    if row_count <= 50:
        csv_str = df.to_csv(index=False)
        return f"Query returned {row_count} rows{truncation_note}:\n\n{csv_str}"

    # For larger results, include summary + first/last rows
    head_str = df.head(20).to_csv(index=False)
    tail_str = df.tail(5).to_csv(index=False, header=False)
    return (
        f"Query returned {row_count} rows{truncation_note}.\n\n"
        f"First 20 rows:\n{head_str}\n"
        f"Last 5 rows:\n{tail_str}\n\n"
        f"Column summary:\n{df.describe(include='all').to_string()}"
    )
