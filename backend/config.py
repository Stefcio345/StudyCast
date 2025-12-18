import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent / "static"
# LLM
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")

# TTS
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "local").lower()
TTS_MODEL = os.getenv("TTS_MODEL", "tts-1")
TTS_VOICE = os.getenv("TTS_VOICE", "alloy")
TTS_VOICE_ALT = os.getenv("TTS_VOICE_ALT", "echo")

# Local Piper
PIPER_COMMAND = os.getenv("PIPER_COMMAND", "piper")
PIPER_MODEL_A = Path(".") / os.getenv("PIPER_MODEL_A", "")
PIPER_MODEL_B = Path(".") / os.getenv("PIPER_MODEL_B", "")
