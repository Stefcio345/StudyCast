# StudyCast — Turn Your Notes Into a Podcast

StudyCast takes your written notes and turns them into clean, listenable audio — so you can “study” by listening while walking, commuting, lifting, cooking, whatever.

You drop in text (lectures, book notes, summaries), StudyCast slices it into segments creates a podcast from them using LLM, runs it through TTS, and gives you an audio file that feels like a mini podcast episode.

---

## Features

### 🎧 Notes → Podcast-style Audio
- Paste your notes or upload text
- Automatically converted into a single continuous audio file
- Ideal for:
  - Exam revision
  - Language learning
  - Long-form reading turned into “pseudo podcast”

### 🔊 Multiple TTS Providers
Supports both **online** and **offline** text-to-speech:

- **OpenAI TTS**
  - High-quality, natural, almost-human voices
  - Great for final “polished” episodes

- **Piper (local TTS)**
  - Runs fully offline on your machine
  - Fast and lightweight
  - Perfect when you don’t want to send data to the cloud

You can pick your provider.

### 🌐 Simple Web UI
<img width="1188" height="729" alt="image" src="https://github.com/user-attachments/assets/ba263fe5-319f-4d32-911c-159544be8895" />
- Clean HTML/CSS/JS frontend
- Paste your notes, choose provider/voice, generate
- See progress while the audio is being processed
- Download the final `.mp3` file directly from the browser

### ⚙️ REST API
Backend powered by **FastAPI**, exposing endpoints like:

```txt
POST /api/process                   → create a new “episode” from text
GET  /api/task_status/{id}          → check processing status
GET  /api/audio/{id}.mp3            → download generated audio
GET  /api/config                    → get current config of backend
POST /api/tasks/{task_id}/cancel    → cancel given task
```

You can script around it, integrate it into other tools, or drive it from your own frontend.

---

## How It Works (High Level)

1. You paste your notes into the UI or call the API.
2. Backend:
   * Normalizes and cleans the text.
   * Splits it into manageable chunks.
   * Sends it to LLM to perform summarization, flashcard generation and podcast script generation
3. You get:
   * Using the generate script program crates dialoge for each person in the script using TTS
   * Then the dialoges are joined into one `.mp3` and are sent to frontend 

---

## Tech Stack

* **Backend**

  * Python 3.12
  * FastAPI
  * OpenAI SDK (for TTS)
  * Piper TTS (local engine)
  * Ollama API
* **Frontend**

  * Vanilla HTML
  * CSS
  * JavaScript (fetch API, progress polling)

---

## Folder Structure

Example structure (may vary slightly depending on your setup):

```txt
StudyCast/
├── backend/
│   ├── main.py               # FastAPI app bootstrap + routing
│   ├── task_manager.py       # Async task registry, cancellation, status tracking
│   ├── llm_adapter.py        # Wrapper for OpenAI/Ollama LLMs (unified interface)
│   ├── config.py             # Configuration, env loading, provider setup
│   ├── ai_client.py          # High-level orchestration: LLM → summary → TTS
│   ├── processing/
│   │   ├── chunker.py        # Splits long input text into TTS-friendly chunks
│   │   ├── extract.py        # Extracts key concepts; builds structured outlines
│   │   ├── flashcards.py     # Generates Q&A flashcards from content
│   │   ├── podcast_gen.py    # Converts text into multi-part “podcast style” narration
│   │   └── summary.py        # Summaries & abstraction layer for note compression
│   ├── audio/
│   │   └── tts.py            # Unified TTS engine (OpenAI + Piper local)
│   └── utils/
│       ├── audio_merge.py    # Merge TTS chunks; normalize & finalize MP3 output
│       └── ids.py            # Generates unique IDs; task ID utilities
├── static/
│   └── frontend/
│       ├── index.html        # Main UI
│       ├── styles.css        # Visuals, waveform mask, animations
│       └── app.js            # Frontend logic: API calls, progress polling, UI updates
├── requirements.txt
└── README.md

```

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/StudyCast.git
cd StudyCast
```

### 2. Create venv and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) Install Piper & models

If you want local TTS:

* Install Piper (via package, pip, or from source)
* Download a voice model (e.g. `en_US`)

Put your models somewhere like:

```bash
mkdir -p piper_models
# place .onnx and .json in ./piper_models
```

---

## Configuration

StudyCast is configured mainly via environment variables.
Check .env file for all the important variables

---

## Running the App

### Backend

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

If the frontend is served by FastAPI’s static files, just go to:

```txt
http://localhost:8000
```

If you’re serving it via another static server, point it at `frontend/` and configure `app.js` to hit the right API URL.

---

## Basic Usage

1. Open the web UI.
2. Paste your notes into the main text area, or attach a pdf of your notes.
3. Choose:
   * TTS provider (OpenAI / local Piper)
   * Voice tone and voice.
   * LLM provider
4. Click **Generate**.
5. Wait for the task to complete (status of task is shown).
6. Download your `.mp3` or listen on the page.

---

## Roadmap

* [x] Multiple voices per episode (e.g. “host” + “guest” style)
* [ ] Automatic intro/outro generation
* [ ] Smart text shortening / LLM-based summarization mode
* [ ] Simple playlist / “course” management
* [ ] Mobile-friendly UI

---

## License

GPL v3.
