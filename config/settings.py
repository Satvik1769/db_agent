import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DB_URL: str = os.environ.get("DB_URL", "")
    DB_POOL_SIZE: int = int(os.environ.get("DB_POOL_SIZE", "5"))
    DB_MAX_OVERFLOW: int = int(os.environ.get("DB_MAX_OVERFLOW", "10"))

    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    QUERY_TIMEOUT_SECONDS: int = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "30"))
    QUERY_ROW_LIMIT: int = int(os.environ.get("QUERY_ROW_LIMIT", "10000"))
    MAX_LLM_RETRIES: int = int(os.environ.get("MAX_LLM_RETRIES", "3"))

    SCHEMA_SAMPLE_ROWS: int = int(os.environ.get("SCHEMA_SAMPLE_ROWS", "3"))

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.environ.get("LOG_FILE", "logs/agent.jsonl")


settings = Settings()
