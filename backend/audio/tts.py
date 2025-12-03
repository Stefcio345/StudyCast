import uuid
from pathlib import Path
import subprocess
from typing import Optional, List, Tuple
import os

from ..config import (
    TTS_PROVIDER,
    TTS_MODEL,
    TTS_VOICE,
    PIPER_COMMAND,
    PIPER_MODEL_A,
    PIPER_MODEL_B,
    BASE_DIR
)

# Try to import optional alt voice, fallback to main voice if missing
try:
    from ..config import TTS_VOICE_ALT  # type: ignore
except ImportError:
    TTS_VOICE_ALT = TTS_VOICE  # type: ignore

from ..ai_client import get_client  # only used if openai

AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG_COMMAND = "ffmpeg"  # assumes ffmpeg is on PATH


def _shorten_for_tts(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars] + "\n\n[... audio truncated for length ...]"


# ---------------------------------------------------------------------------
# SCRIPT PARSING FOR MULTI-SPEAKER TTS
# ---------------------------------------------------------------------------

def _parse_dialogue_segments(script: str) -> List[Tuple[str, str]]:
    """
    Parse the podcast script into segments by speaker.

    Expected format:
      [00:00] A: Hello...
      [00:05] B: Hi...

    or:
      A: Hello...
      B: Hi...

    Returns list of (voice_name, text).
    """
    lines = script.splitlines()
    segments: List[Tuple[str, str]] = []

    def voice_for_speaker(tag: str) -> str:
        # Basic mapping: A -> TTS_VOICE, B -> TTS_VOICE_ALT
        t = tag.upper()
        if t == "A":
            return TTS_VOICE
        elif t == "B":
            return TTS_VOICE_ALT
        # default narrator
        return TTS_VOICE

    current_voice: Optional[str] = None
    current_text_parts: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        speaker_tag: Optional[str] = None
        content = line

        # Strip timestamp if present: [00:00] A: ...
        if content.startswith("[") and "]" in content:
            closing = content.find("]")
            content_after_time = content[closing + 1 :].lstrip()
        else:
            content_after_time = content

        # Detect "A:" / "B:" prefix
        if len(content_after_time) >= 2 and content_after_time[1] == ":":
            # e.g. "A:" or "B:"
            maybe_speaker = content_after_time[0]
            if maybe_speaker.upper() in ("A", "B"):
                speaker_tag = maybe_speaker.upper()
                content = content_after_time[2:].lstrip()
            else:
                content = content_after_time
        else:
            content = content_after_time

        # Decide voice for this line
        if speaker_tag is None:
            voice = TTS_VOICE  # narrator default
        else:
            voice = voice_for_speaker(speaker_tag)

        # Group consecutive lines with same voice into one segment
        if current_voice is None:
            current_voice = voice
            current_text_parts = [content]
        else:
            if voice == current_voice:
                current_text_parts.append(content)
            else:
                # flush previous
                segments.append((current_voice, "\n".join(current_text_parts)))
                current_voice = voice
                current_text_parts = [content]

    # flush last
    if current_voice is not None and current_text_parts:
        segments.append((current_voice, "\n".join(current_text_parts)))

    # If we somehow failed to detect any structured segments, fall back to single segment
    if not segments and script.strip():
        segments.append((TTS_VOICE, script.strip()))

    return segments


def _concat_audio_files_mp3(paths: List[Path], output_path: Path) -> None:
    """
    Concatenate multiple mp3 files into one using ffmpeg concat demuxer.
    """
    if not paths:
        raise ValueError("No audio files to concatenate")

    list_file = output_path.with_suffix(".txt")
    with list_file.open("w", encoding="utf-8") as f:
        for p in paths:
            # ffmpeg concat file format: file 'path'
            f.write(f"file '{p.as_posix()}'\n")

    cmd = [
        FFMPEG_COMMAND,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(output_path),
    ]

    subprocess.run(cmd, check=True)
    list_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# OPENAI TTS
# ---------------------------------------------------------------------------

def _generate_tts_openai(script: str) -> str:
    """
    OpenAI TTS wrapper with multi-voice support.

    - Parses script and assigns voices by speaker.
    - Generates one mp3 per segment.
    - Concatenates them into a single mp3.
    """
    client = get_client()

    # Parse script into (voice, text) segments
    segments = _parse_dialogue_segments(script)
    if not segments:
        return ""

    file_id = uuid.uuid4().hex
    final_filename = f"{file_id}.mp3"
    final_path = AUDIO_DIR / final_filename

    segment_paths: List[Path] = []

    try:
        # 1) Generate audio for each segment
        for idx, (voice, text) in enumerate(segments):
            safe_text = _shorten_for_tts(text)
            safe_text = safe_text.strip()
            if not safe_text:
                safe_text = "."
            seg_filename = f"{file_id}_seg_{idx}.mp3"
            seg_path = AUDIO_DIR / seg_filename

            try:
                resp = client.audio.speech.create(
                    model=TTS_MODEL,
                    voice=voice,
                    input=safe_text,
                )

                audio_bytes = None

                # NEWER SDKs: resp.data
                if hasattr(resp, "data") and isinstance(resp.data, (bytes, bytearray)):
                    audio_bytes = resp.data

                # Some versions: resp.audio
                elif hasattr(resp, "audio") and isinstance(resp.audio, (bytes, bytearray)):
                    audio_bytes = resp.audio

                # Older-style: .read()
                elif hasattr(resp, "read"):
                    audio_bytes = resp.read()

                # Very old fallback
                elif hasattr(resp, "output"):
                    try:
                        audio_bytes = resp.output[0].content[0].audio
                    except Exception:
                        pass

                if audio_bytes is None:
                    raise RuntimeError("Unsupported TTS response object: no audio bytes found.")

                with open(seg_path, "wb") as f:
                    f.write(audio_bytes)

                segment_paths.append(seg_path)

            except Exception as e:
                if "401" in str(e) or "No API key" in str(e) or "invalid_api_key" in str(e):
                    raise ValueError("OpenAI API key is missing or invalid.") from e
                print(f"OpenAI TTS error on segment {idx}:", e)
                # If any segment fails, bail out
                for p in segment_paths:
                    p.unlink(missing_ok=True)
                return ""

        # 2) Concatenate into final file
        if len(segment_paths) == 1:
            # Single segment -> just rename
            segment_paths[0].rename(final_path)
        else:
            _concat_audio_files_mp3(segment_paths, final_path)
            # cleanup segment files
            for p in segment_paths:
                p.unlink(missing_ok=True)

        return f"/static/audio/{final_filename}"
    except ValueError as e:
        raise ValueError("OpenAI API key is missing or invalid.") from e
    except Exception as e:
        print("OpenAI TTS error:", e)
        # cleanup on any top-level failure
        for p in segment_paths:
            p.unlink(missing_ok=True)
        if final_path.exists():
            final_path.unlink()
        return ""


# ---------------------------------------------------------------------------
# LOCAL PIPER TTS (unchanged)
# ---------------------------------------------------------------------------

def _generate_tts_local_piper(script: str) -> str:
    """
    Multi-speaker Piper TTS.
    - Reuses dialogue parser (A/B speakers)
    - Uses two Piper models, one per speaker
    - Concatenates segments into a single audio file
    """
    segments = _parse_dialogue_segments(script)
    if not segments:
        segments = [(None, script)]

    file_id = uuid.uuid4().hex
    final_filename = f"{file_id}.wav"
    final_path = AUDIO_DIR / final_filename

    segment_files = []

    if not os.path.exists(PIPER_MODEL_A):
        raise FileNotFoundError(f"Model file not found: {PIPER_MODEL_A}")

    if not os.path.exists(PIPER_MODEL_B):
        raise FileNotFoundError(f"Model file not found: {PIPER_MODEL_B}")

    try:
        for idx, (voice, text) in enumerate(segments):
            # Decide which Piper model to use
            if voice == TTS_VOICE:
                model = PIPER_MODEL_A
            else:
                model = PIPER_MODEL_B

            safe_text = _shorten_for_tts(text, max_chars=1200)

            seg_path = AUDIO_DIR / f"{file_id}_seg_{idx}.wav"


            cmd = [
                PIPER_COMMAND,
                "--model", str(model),
                "--output_file", str(seg_path),
                "--length_scale", "0.9",
                "--noise_scale", "0.5",
                "--noise_w", "0.7",
            ]

            try:
                subprocess.run(
                    cmd,
                    input=safe_text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )

            except subprocess.CalledProcessError as e:
                print(f"Piper TTS error on segment {idx}: {e.stderr.decode('utf-8', 'ignore')}")
                # optionally continue instead of killing the whole job
                continue

            segment_files.append(seg_path)

        # concatenate segments
        list_file = final_path.with_suffix(".txt")
        with list_file.open("w") as f:
            for seg in segment_files:
                f.write(f"file '{seg.as_posix()}'\n")

        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(final_path)
        ]
        subprocess.run(concat_cmd, check=True)

        # cleanup
        list_file.unlink(missing_ok=True)
        for p in segment_files:
            p.unlink(missing_ok=True)

        return f"/static/audio/{final_filename}"

    except Exception as e:
        print("Piper multi-voice TTS error:", e)
        return ""



def generate_tts_audio(script: str, provider: Optional[str] = None) -> str:
    """
    Unified TTS entry point.

    provider:
      - overrides TTS_PROVIDER if provided
      - openai / local / none
    """
    use_provider = (provider or TTS_PROVIDER).lower()
    if use_provider == "openai":
        return _generate_tts_openai(script)
    elif use_provider == "local":
        return _generate_tts_local_piper(script)
    elif use_provider == "none":
        return ""
    else:
        print(f"Unsupported TTS provider: {use_provider}")
        return ""
