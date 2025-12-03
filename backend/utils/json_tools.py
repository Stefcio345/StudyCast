# backend/utils/json_tools.py

import json
import re

def try_json_load(text: str):
    """
    Safely parse a JSON string returned by an LLM.
    - Handles JSON with code fences
    - Handles leading/trailing junk
    - Returns None on failure
    """
    if not isinstance(text, str):
        return None

    clean = text.strip()

    # Remove ```json ... ``` or ``` ... ```
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"```$", "", clean).strip()

    # Try direct parse
    try:
        return json.loads(clean)
    except Exception:
        pass

    # Try extracting first JSON {...} or [...] block
    try:
        match = re.search(r"(\{.*\}|\[.*\])", clean, flags=re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except Exception:
        pass

    return None
