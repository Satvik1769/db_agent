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
Then open `schema/metadata.yaml` and fill in `description` and `notes` fields for tables and columns.
The more context you provide, the better the agent's answers.

**4. (Optional) Add business rules**

Edit `config/business_rules.md` to teach the agent domain-specific table disambiguation rules — e.g. which table is authoritative for revenue, which tables are commodity-only, how monetary columns are denominated, etc.

These rules are injected verbatim into every system prompt and are re-read on each query, so edits take effect immediately without restarting.

**5. Launch**
```bash
streamlit run main.py
```

## Usage

- Type any natural language question about your data
- The agent writes SQL, executes it, and interprets the results
- Generated SQL is shown in an expandable block for transparency
- Multi-turn: follow up with "now break that down by X" or "filter to last month"

## Improving Query Accuracy

### Table `notes` field

Each table in `schema/metadata.yaml` supports a `notes` field (separate from `description`) for business-context annotations:

```yaml
user_current_subscription:
  description: ''
  notes: 'Primary authoritative table for all subscription revenue and mandate payments.
    Prefer over commodity_user_subscription unless user explicitly asks about commodity products.'
```

Notes are scored with high weight (2.5×) during table selection and rendered prominently in the schema context sent to the LLM.

### Business rules file

`config/business_rules.md` is a plain Markdown file defining cross-table disambiguation rules. Add rules for any domain where the agent might pick the wrong table:

```markdown
## Subscriptions
- For mandate revenue queries, use `user_current_subscription`.
- Only use `commodity_user_subscription` for F&O/MCX-specific queries.
```

### How table selection works

For each query the agent:
1. Tokenizes the question and scores all tables by relevance (table name: 3×, notes: 2.5×, column names: 2×, description: 1.5×, column descriptions: 1×)
2. Applies a domain-prefix penalty — tables whose prefix token (e.g. `commodity`) is absent from the query are deprioritized in ties
3. Passes the top 15 tables plus the full business rules to the LLM

## Security

- Database connection is enforced read-only at the PostgreSQL session level
- All queries are validated before execution (SELECT/WITH only)
- Query timeout: 30s | Row limit: 10,000 rows

## Project Structure

```
config/        Settings loaded from .env; business_rules.md for domain guidance
db/            Database connection and SQL execution
schema/        Schema introspection, catalog, table selector, and context building
agent/         LLM integration (Claude/OpenAI) and agentic loop
ui/            Streamlit interface
logging_/      Structured JSON logging
scripts/       Developer utilities (DB introspection, metadata generation)
logs/          Turn-by-turn JSONL logs (gitignored)
```
