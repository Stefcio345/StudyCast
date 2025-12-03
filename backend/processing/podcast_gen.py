from typing import Literal, Optional, Awaitable, Callable
from .chunker import chunk_text
from ..llm_adapter import llm_chat

ToneStyle = Literal["dynamic_duo", "serious_prof", "casual_friend", "anime_senpai"]
CancelCheck = Callable[[], Awaitable[None]]


def _style_description(style: str) -> str:
    mapping = {
        "dynamic_duo": "Two friendly podcast hosts with light banter",
        "serious_prof": "A serious professor and a student",
        "casual_friend": "Two casual friends explaining things simply",
        "anime_senpai": "Senpai explaining concepts to kouhai in anime style (still technically correct, no cringe)",
    }
    return mapping.get(style, "Two people discussing the topic")


async def build_podcast_script(
    extracted_text: str,
    duration_minutes: int,
    style: ToneStyle,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    cancel_check: Optional[CancelCheck] = None,
) -> str:
    chunks = chunk_text(extracted_text, max_chars=3000, overlap=300)
    joined = "\n\n".join(chunks)

    style_desc = _style_description(style)

    system_content = (
        "You are a podcast script writer. You turn study material into "
        "engaging, clear dialogues between exactly two speakers: A and B."
    )

    user_content = f"""Create a podcast script from the following study material.

Study material:
{joined}

Requirements:
- Two speakers only: 'A:' and 'B:'.
- Tone style: {style_desc}.
- Target duration: about {duration_minutes} minutes (approximate).
- Use timestamp tags in format [mm:ss] at reasonable intervals (every few lines).
- Start at [00:00].
- No meta commentary about 'summarizing' or 'this is a script'.
- Directly output the final script.
"""

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    if cancel_check:
        await cancel_check()  # <-- before LLM call

    script = await llm_chat(
        messages,
        provider=llm_provider,
        model=llm_model,
    )
    return script
