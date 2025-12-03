from fastapi import FastAPI, UploadFile, File, Form, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import requests
import logging
import traceback

from .task_manager import (
    TaskCancelledError,
    create_task,
    cancel_task,
    clear_task,
    make_cancel_check,
    set_stage,
    get_task,
    get_queue_position
)

from .config import (
    LLM_PROVIDER,
    OPENAI_MODEL,
    OLLAMA_MODEL,
    OLLAMA_URL,
    TTS_PROVIDER,
    TTS_MODEL,
    TTS_VOICE,
    BASE_DIR
)
from .processing.extract import extract_text_from_inputs
from .processing.summary import summarize_text
from .processing.flashcards import build_flashcards
from .processing.podcast_gen import build_podcast_script
from .audio.tts import generate_tts_audio

logger = logging.getLogger(__name__)

def _get_ollama_models() -> list[str]:
  try:
      # derive base URL from OLLAMA_URL if needed
      base = OLLAMA_URL.split("/api")[0].rstrip("/")
      tags_url = f"{base}/api/tags"
      resp = requests.get(tags_url, timeout=2)
      resp.raise_for_status()
      data = resp.json()
      return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
  except Exception as e:
      print("Could not fetch Ollama models:", e)
      return []

app = FastAPI(title="StudyCast Backend", version="0.1.0")

# Static files (for audio)
BASE_DIR.mkdir(exist_ok=True)
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_HTML = FRONTEND_DIR / "index.html"
(app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static"))


# CORS so you can open frontend from file:// or localhost:*
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # be stricter in prod if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def index():
    # Serve the main HTML
    return FileResponse(str(INDEX_HTML))

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/config")
async def get_config():
    ollama_models = _get_ollama_models()

    return {
        "llm": {
            "default_provider": LLM_PROVIDER,
            "providers": ["openai", "ollama"],
            "openai_model": OPENAI_MODEL,
            "default_ollama_model": OLLAMA_MODEL,
            "ollama_models": ollama_models,
        },
        "tts": {
            "default_provider": TTS_PROVIDER,
            "providers": ["openai", "local", "none"],
            "openai_model": TTS_MODEL,
            "openai_voice": TTS_VOICE,
        },
    }

@app.get("/api/task_status/{task_id}")
async def task_status(task_id: str):
    state = get_task(task_id)
    if not state:
        return JSONResponse(status_code=404, content={"error": "Unknown task"})

    queue_pos = get_queue_position(task_id)

    return {
        "taskId": state.id,
        "stage": state.stage,
        "cancelled": state.cancelled,
        "createdAt": state.created_at.isoformat() + "Z",
        "queuePosition": queue_pos
    }

@app.post("/api/tasks/{task_id}/cancel")
async def cancel_generation(task_id: str):
    if not task_id:
        return JSONResponse(status_code=400, content={"error": "task_id required"})

    cancel_task(task_id)
    print(f"[/api/cancel] task {task_id} marked as cancelled")
    return {"status": "ok"}

@app.post("/api/process")
async def process(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    text: str = Form(""),
    duration: int = Form(5),
    style: str = Form("dynamic_duo"),
    llm_provider: Optional[str] = Form(default=None),
    llm_model: Optional[str] = Form(default=None),
    tts_provider: Optional[str] = Form(default=None),
    task_id: Optional[str] = Form(default=None),
):
    if not task_id:
        import uuid
        task_id = str(uuid.uuid4())

    create_task(task_id)
    set_stage(task_id, "queued")

    cancel_check = make_cancel_check(request, task_id)

    print(
        "[/api/process] task_id=", task_id,
        "llm_provider=", repr(llm_provider),
        "llm_model=", repr(llm_model),
        "tts_provider=", repr(tts_provider),
    )

    try:
        await cancel_check()

        # 1) Extract text
        set_stage(task_id, "extracting")
        extracted = await extract_text_from_inputs(file=file, text=text)

        # 2) Summary
        set_stage(task_id, "summary")
        summary = await summarize_text(
            extracted,
            max_bullets=1,
            llm_provider=llm_provider,
            llm_model=llm_model,
            cancel_check=cancel_check,
        )

        # 3) Flashcards
        set_stage(task_id, "flashcards")
        await cancel_check()
        flashcards = await build_flashcards(
            extracted,
            limit=1,
            llm_provider=llm_provider,
            llm_model=llm_model,
            cancel_check=cancel_check,
        )

        # 4) Script
        set_stage(task_id, "script")
        await cancel_check()
        script = await build_podcast_script(
            extracted_text=extracted,
            duration_minutes=duration,
            style=style,
            llm_provider=llm_provider,
            llm_model=llm_model,
            cancel_check=cancel_check,
        )

        # 5) Audio
        set_stage(task_id, "audio")
        await cancel_check()
        audio_url = generate_tts_audio(script, provider=tts_provider)

        set_stage(task_id, "done")
        return {
            "summary": summary,
            "flashcards": flashcards,
            "script": script,
            "audioUrl": audio_url,
            "taskId": task_id,
        }

    except TaskCancelledError:
        set_stage(task_id, "cancelled")
        print(f"[/api/process] Task {task_id} cancelled or disconnected.")
        return JSONResponse(
            status_code=499,
            content={"error": "Client disconnected or cancelled"},
        )
    except ValueError as e:
        set_stage(task_id, "error")
        return JSONResponse(status_code=400, content={"error": str(e)})
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"error": str(e)})
    except Exception as e:
        set_stage(task_id, "error")
        logger.error("[/api/process] Unexpected error:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"},
        )
    #finally:
        # NOTE: if you want to inspect state later, you can skip clear_task here
        # clear_task(task_id)

