# db_agent

AI-powered database Q&A agent. Ask questions in plain English, get SQL-backed answers.

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure environment**
```bash
cp .env.example .env
# Edit .env with your PostgreSQL URL and Anthropic API key
```

**3. Introspect your database schema**
```bash
python scripts/introspect_db.py
```
Then open `schema/metadata.yaml` and fill in `description` fields for tables and columns.
The more context you provide, the better the agent's answers.

**4. Launch**
```bash
streamlit run main.py
```

## Usage

- Type any natural language question about your data
- The agent writes SQL, executes it, and interprets the results
- Generated SQL is shown in an expandable block for transparency
- Multi-turn: follow up with "now break that down by X" or "filter to last month"

## Security

- Database connection is enforced read-only at the PostgreSQL session level
- All queries are validated before execution (SELECT/WITH only)
- Query timeout: 30s | Row limit: 10,000 rows

## Project Structure

```
config/        Settings loaded from .env
db/            Database connection and SQL execution
schema/        Schema introspection, catalog, and context building
agent/         Claude API integration and agentic loop
ui/            Streamlit interface
logging_/      Structured JSON logging
scripts/       Developer utilities (DB introspection)
logs/          Turn-by-turn JSONL logs (gitignored)
```
