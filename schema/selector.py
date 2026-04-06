import re

from schema.catalog import EnrichedTable

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "on", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "from", "up", "down", "out", "off", "over", "under",
    "again", "further", "then", "once", "and", "but", "or", "nor", "so",
    "yet", "both", "either", "neither", "not", "only", "own", "same",
    "than", "too", "very", "just", "how", "many", "much", "what", "when",
    "where", "which", "who", "whom", "this", "that", "these", "those",
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "she",
    "it", "its", "they", "them", "their", "all", "each", "every", "list",
    "show", "give", "tell", "get", "find", "return", "display",
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _score_table(query_tokens: set[str], table: EnrichedTable) -> float:
    score = 0.0

    # Table name match (high weight)
    table_tokens = _tokenize(table.name)
    overlap = query_tokens & table_tokens
    score += len(overlap) * 3.0

    # Table description match
    if table.description:
        desc_tokens = _tokenize(table.description)
        score += len(query_tokens & desc_tokens) * 1.5

    # Table notes match (business guidance — high weight)
    if table.notes:
        notes_tokens = _tokenize(table.notes)
        score += len(query_tokens & notes_tokens) * 2.5

    # Column name matches
    for col in table.columns:
        col_tokens = _tokenize(col.name)
        col_overlap = query_tokens & col_tokens
        if col_overlap:
            score += len(col_overlap) * 2.0

        # Column description matches
        if col.description:
            col_desc_tokens = _tokenize(col.description)
            score += len(query_tokens & col_desc_tokens) * 1.0

        # Enum value matches
        if col.enum_values:
            for val in col.enum_values:
                if str(val).lower() in query_tokens:
                    score += 1.5

    return score


def select_relevant_tables(
    question: str,
    all_tables: dict[str, EnrichedTable],
    max_tables: int = 15,
) -> dict[str, EnrichedTable]:
    if len(all_tables) <= max_tables:
        return all_tables

    query_tokens = _tokenize(question)
    if not query_tokens:
        # No meaningful tokens — return first max_tables alphabetically
        sorted_names = sorted(all_tables.keys())
        return {name: all_tables[name] for name in sorted_names[:max_tables]}

    scores = {
        name: _score_table(query_tokens, table)
        for name, table in all_tables.items()
    }

    def _domain_prefix_penalty(table_name: str) -> float:
        """Penalize tables whose domain-prefix token is absent from the query.
        E.g. 'commodity_*' tables get penalized when the query has no 'commodity' token.
        """
        first_token = table_name.split("_")[0].lower()
        if first_token not in _STOPWORDS and first_token not in query_tokens and len(first_token) > 2:
            return 1.0
        return 0.0

    # Sort by score descending; ties broken by domain-prefix relevance, then alphabetical
    ranked = sorted(scores.items(), key=lambda x: (-x[1], _domain_prefix_penalty(x[0]), x[0]))
    selected = [name for name, _ in ranked[:max_tables]]

    return {name: all_tables[name] for name in selected}
