import asyncio
from typing import List, Dict, Optional
import requests

from .config import (
    LLM_PROVIDER,
    OPENAI_MODEL,
    OLLAMA_MODEL,
    OLLAMA_URL,
)
from .ai_client import get_client


async def llm_chat(
    messages: List[Dict[str, str]],
    *,
    json_mode: bool = False,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    provider = (provider or LLM_PROVIDER).lower()

    if provider == "openai":
        def _call_openai() -> str:
            client = get_client()
            use_model = model or OPENAI_MODEL

            resp = client.responses.create(
                model=use_model,
                input=messages,
            )

            # Try high-level helper if present
            text = getattr(resp, "output_text", None)
            if text is None:
                # Fallback for older response objects
                try:
                    text = resp.output[0].content[0].text
                except Exception:
                    text = str(resp)
            return text.strip()

        return await asyncio.to_thread(_call_openai)

    elif provider == "ollama":
        def _call_ollama() -> str:
            use_model = model or OLLAMA_MODEL
            payload = {
                "model": use_model,
                "messages": messages,
                "stream": False,
            }
            print("[llm_chat] Using Ollama model:", use_model)
            try:
                resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
                resp.raise_for_status()
            except requests.RequestException as e:
                print("[llm_chat] Ollama request failed:", e)
                raise RuntimeError(
                    "Could not reach local Ollama server. Is it running on 127.0.0.1:11434?"
                ) from e
            data = resp.json()
            msg = data.get("message", {})
            content = msg.get("content", "")
            return content.strip()

        return await asyncio.to_thread(_call_ollama)

    else:
        raise RuntimeError(f"Unsupported LLM provider: {provider}")
