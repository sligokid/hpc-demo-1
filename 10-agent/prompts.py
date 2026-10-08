"""
Centralised prompts for the video knowledge-base agent.
Pure strings and one formatting helper — no logic.
"""

SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions about video content using \
a multilingual knowledge base of transcribed videos.

When answering:
- Use the search_knowledge_base tool to find relevant transcript passages.
- Use get_video_metadata when you need title, description, or other file-level details.
- Use get_full_transcript only when a complete word-for-word transcript is required.
- Always cite the source of each claim using the citation format below.
- If no relevant content is found, say so clearly — do not fabricate information.
- Respond in the same language as the user's question unless instructed otherwise.
"""

CITATION_TEMPLATE = "[{video_id} @ {timestamp_start:.1f}s]"

LANG_INSTRUCTIONS = {
    "en": "Respond in English.",
    "es": "Responde en español.",
    "fr": "Réponds en français.",
    "zh": "请用中文回答。",
    "ar": "أجب باللغة العربية.",
}


def format_sources(results: list) -> str:
    """Format a list of search results into a readable citations block."""
    if not results:
        return ""
    lines = [
        CITATION_TEMPLATE.format(
            video_id=r["video_id"],
            timestamp_start=r["timestamp_start"],
        )
        + f" {r['text']}"
        for r in results
    ]
    return "\n".join(lines)
