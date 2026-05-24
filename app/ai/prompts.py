"""Centralized prompt templates for AI recall.

Rules (ai-module.md):
  - ALL prompts live here. No inline prompt strings anywhere else in the codebase.
  - Never log user prompts or assistant responses in full — only previews.
  - Keep prompts deterministic (low temperature, specific format instructions).
"""

from __future__ import annotations

# ── System prompt ─────────────────────────────────────────────────────────

RECALL_SYSTEM_PROMPT = """\
You are MyLogMate's AI assistant — a helpful, concise work-log analyst.

Your job is to answer questions about a user's past work log entries.
You are given a set of relevant log excerpts (date range + content) as context.

Guidelines:
- Answer only from the provided log context. Do not hallucinate details.
- If the context does not contain enough information, say so clearly.
- Be concise. Prefer bullet points for lists. Use clear section headers when needed.
- Dates matter. Reference specific dates when they help the answer.
- Do NOT reveal the internal structure of how logs are stored.
- Do NOT repeat the user's question back to them.
- NEVER ask for clarification — do your best with the available context.
"""

# ── Context block template ────────────────────────────────────────────────

_LOG_ENTRY_TEMPLATE = """\
[{date_start}]
{content}
"""


def build_context_block(log_hits: list[dict[str, object]]) -> str:
    """Format retrieved log hits into a readable context block for the LLM.

    Args:
        log_hits: List of payload dicts from Qdrant — each has at minimum:
                  {"log_id": str, "date_start": str, "content": str, ...}

    Returns:
        A formatted string of log entries separated by blank lines.
        Returns an empty string if log_hits is empty.
    """
    if not log_hits:
        return ""

    blocks: list[str] = []
    for hit in log_hits:
        date_start = str(hit.get("date_start", "unknown date"))
        content = str(hit.get("content", ""))
        blocks.append(_LOG_ENTRY_TEMPLATE.format(date_start=date_start, content=content))

    return "\n".join(blocks)


def build_recall_messages(
    user_query: str,
    context_block: str,
) -> list[dict[str, str]]:
    """Construct the full message list for the LLM recall query.

    Args:
        user_query: The user's natural-language question.
        context_block: Formatted string of relevant log entries.

    Returns:
        List of {"role": ..., "content": ...} dicts ready for BaseLLMProvider.acomplete().
    """
    if context_block:
        user_content = (
            f"Here are some of my relevant work log entries:\n\n"
            f"{context_block}\n\n"
            f"Question: {user_query}"
        )
    else:
        user_content = (
            f"I don't have any log entries matching that query.\n\n"
            f"Question: {user_query}"
        )

    return [
        {"role": "system", "content": RECALL_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
