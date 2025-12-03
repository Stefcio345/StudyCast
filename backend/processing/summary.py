from typing import List, Optional, Awaitable, Callable
from .chunker import chunk_text
from ..llm_adapter import llm_chat

CancelCheck = Callable[[], Awaitable[None]]  # async () -> None


async def summarize_text(
    text: str,
    max_bullets: int = 5,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    cancel_check: Optional[CancelCheck] = None,
) -> str:
    chunks = chunk_text(text, max_chars=2500, overlap=300)
    chunk_summaries: List[str] = []

    for ch in chunks:
        if cancel_check:
            await cancel_check()  # <-- check before each LLM call

        messages = [
            {
                "role": "system",
                "content": "You are a study assistant.",
            },
            {
                "role": "user",
                "content": f"""Summarize the following study material in bullet points.

Rules:
- Maximum {max_bullets} bullets.
- Very clear, exam-friendly.
- No fluff.

Text:
{ch}
""",
            },
        ]
        summary = await llm_chat(
            messages,
            provider=llm_provider,
            model=llm_model,
        )
        chunk_summaries.append(summary)

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    joined = "\n".join(chunk_summaries)

    if cancel_check:
        await cancel_check()  # before combine call

    messages = [
        {
            "role": "system",
            "content": "You are a concise study assistant.",
        },
        {
            "role": "user",
            "content": f"""You will get several bullet-point summaries, one per chunk of a larger text.

Condense them into at most {max_bullets} extremely clear, exam-oriented bullet points.

Input summaries:
{joined}
""",
        },
    ]
    combined = await llm_chat(
        messages,
        provider=llm_provider,
        model=llm_model,
    )
    return combined
