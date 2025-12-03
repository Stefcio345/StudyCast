from openai import OpenAI
from .config import OPENAI_API_KEY

_client = None

def get_client():
    global _client
    if _client is None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY missing but LLM_PROVIDER=openai")
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client
