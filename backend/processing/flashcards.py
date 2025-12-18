from typing import List, Dict, Optional, Awaitable, Callable
from .chunker import chunk_text
from ..llm_adapter import llm_chat
from ..utils.json_tools import try_json_load

CancelCheck = Callable[[], Awaitable[None]]


async def build_flashcards(
    text: str,
    limit: int = 10,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    cancel_check: Optional[CancelCheck] = None,
) -> List[Dict[str, str]]:

    chunks = chunk_text(text, max_chars=3000, overlap=0)
    base = chunks[0]

    prompt = f"""You are a study assistant.

From the following text, generate up to {limit} flashcards.

Rules:
- Only return JSON.
- Preferred format: [{{"question": "...", "answer": "..."}}, ...]
- If there is only ONE flashcard, you may also return a single JSON object: {{"question": "...", "answer": "..."}}.
- No markdown, no commentary, no code fences.

Text:
{base}
"""

    messages = [
        {"role": "system", "content": "You output ONLY JSON (object or array)."},
        {"role": "user", "content": prompt},
    ]

    if cancel_check:
        await cancel_check()

    raw = await llm_chat(
        messages,
        json_mode=True,
        provider=llm_provider,
        model=llm_model,
    )

    parsed = try_json_load(raw)

    # --- accept both object and array ---
    if isinstance(parsed, dict):
        parsed_list = [parsed]
    elif isinstance(parsed, list):
        parsed_list = parsed
    else:
        print("[flashcards] Could not parse JSON, raw was:")
        print(raw)
        return [
            {
                "question": "Unable to parse flashcards",
                "answer": "Model returned invalid JSON or unsupported structure.",
            }
        ]

    out: List[Dict[str, str]] = []
    for item in parsed_list[:limit]:
        q = str(item.get("question", "")).strip()
        a = str(item.get("answer", "")).strip()
        if q and a:
            out.append({"question": q, "answer": a})

    if not out:
        out = [
            {
                "question": "No valid flashcards",
                "answer": "Model produced empty or invalid data.",
            }
        ]

    return out
