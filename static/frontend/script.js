// --- DOM refs -------------------------------------------------------------

const fileInput = document.getElementById("fileInput");
const fileNameLabel = document.getElementById("fileName");
const textInput = document.getElementById("textInput");
const durationSelect = document.getElementById("durationSelect");
const styleSelect = document.getElementById("styleSelect");
const generateBtn = document.getElementById("generateBtn");
const statusText = document.getElementById("statusText");
const loadingIndicator = document.getElementById("loadingIndicator");
const cancelBtn = document.getElementById("cancelBtn");

const llmProviderSelect = document.getElementById("llmProviderSelect");
const llmModelSelect = document.getElementById("llmModelSelect");
const ttsProviderSelect = document.getElementById("ttsProviderSelect");

const tabButtons = document.querySelectorAll(".tab-button");
const tabContents = document.querySelectorAll(".tab-content");

const summaryContent = document.getElementById("summaryContent");
const scriptContent = document.getElementById("scriptContent");
const flashcardsContent = document.getElementById("flashcardsContent");

//AUDIO PLAYER
const audioPlayer = document.getElementById("audioPlayer");
const audioDownload = document.getElementById("audioDownload");
const audioPlaceholder = document.getElementById("audioPlaceholder");
const audioPlayerShell = document.getElementById("audioPlayerShell");
const audioPlayPause = document.getElementById("audioPlayPause");
const audioCurrentEl = document.getElementById("audioCurrent");
const audioDurationEl = document.getElementById("audioDuration");
const audioProgressFill = document.getElementById("audioProgressFill");
const audioWaveform = document.getElementById("audioWaveform");

let waveformBars = [];

let currentAbortController = null;
let currentTaskId = null;

const STATUS_LABELS = {
  queued: "Queued…",
  extracting: "Extracting content…",
  summary: "Generating summary…",
  flashcards: "Generating flashcards…",
  script: "Creating podcast script…",
  audio: "Generating audio…",
  done: "Completed!",
  cancelled: "Cancelled.",
  error: "Error.",
};

const progressSteps = document.querySelectorAll(".progress-step");
let statusPollInterval = null;

// --- File name display ----------------------------------------------------

fileInput.addEventListener("change", () => {
  const file = fileInput.files?.[0];
  if (file) {
    fileNameLabel.textContent = file.name;
    fileNameLabel.classList.add("has-file");
  } else {
    fileNameLabel.textContent = "Drop PDF here or click to browse";
    fileNameLabel.classList.remove("has-file");
  }
});

// --- Tabs ---------------------------------------------------------------

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.getAttribute("data-tab");

    tabButtons.forEach((b) => b.classList.remove("active"));
    tabContents.forEach((c) => c.classList.remove("active"));

    btn.classList.add("active");
    const targetEl = document.getElementById(target);
    if (targetEl) targetEl.classList.add("active");
  });
});

// --- Config loader + cache ------------------------------------------------

let backendConfig = null;

async function loadBackendConfig() {
  try {
    const res = await fetch("http://127.0.0.1:8000/api/config");
    if (!res.ok) throw new Error("Failed to fetch config");
    backendConfig = await res.json();

    console.log("Backend config:", backendConfig);

    const llm = backendConfig.llm;

    resetLlmModelSelect();

    if (!llmProviderSelect.value) {
      llmProviderSelect.value = llm.default_provider;
    }

    const currentProvider = llmProviderSelect.value;
    if (currentProvider === "ollama") {
      resetLlmModelSelect(llm.ollama_models);
    } else {
      resetLlmModelSelect(); // Auto only
    }
  } catch (e) {
    console.error(e);
  }
}

function prettyModelName(modelName) {
  // 1. Remove the ":tag" part
  const base = modelName.split(":")[0];   // "llama3.2"

  // 2. Extract prefix (letters) and suffix (digits)
  const match = base.match(/^([a-zA-Z]+)([\d\.]+.*)?$/);

  if (!match) {
    // fallback: capitalize first letter
    return base.charAt(0).toUpperCase() + base.slice(1);
  }

  const rawPrefix = match[1]; // llama
  const rawVersion = match[2] || ""; // 3.2

  // Capitalize prefix
  const prefix =
    rawPrefix.charAt(0).toUpperCase() + rawPrefix.slice(1).toLowerCase();

  // Insert space only if version exists (e.g., "3.2")
  if (rawVersion) return `${prefix} ${rawVersion}`;

  return prefix;
}

function resetLlmModelSelect(models = []) {
  llmModelSelect.innerHTML = "";

  if (models.length === 0) {
    const autoOpt = document.createElement("option");
    autoOpt.value = "";
    autoOpt.textContent = "Auto";
    llmModelSelect.appendChild(autoOpt);
    return;
  }

  models.forEach((modelName) => {
    const opt = document.createElement("option");

    // Send real model name to backend
    opt.value = modelName;

    // Pretty label for UI
    opt.textContent = prettyModelName(modelName);

    llmModelSelect.appendChild(opt);
  });
}
// When provider changes, update model list for Ollama
llmProviderSelect.addEventListener("change", () => {
  if (!backendConfig) {
    resetLlmModelSelect();
    return;
  }
  const provider = llmProviderSelect.value;
  if (provider === "ollama") {
    const ollamaModels = backendConfig.llm.ollama_models || [];
    resetLlmModelSelect(ollamaModels);
  } else {
    resetLlmModelSelect(); // just Auto
  }
});

// Kick off config load
loadBackendConfig();

// --- Audio Player ---------------------------------------------------------

function formatTime(seconds) {
  if (!isFinite(seconds)) return "0:00";
  const s = Math.floor(seconds);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}

// Update duration when metadata loaded
audioPlayer.addEventListener("loadedmetadata", () => {
  audioDurationEl.textContent = formatTime(audioPlayer.duration || 0);
});

audioPlayer.addEventListener("timeupdate", () => {
  audioCurrentEl.textContent = formatTime(audioPlayer.currentTime);

  if (!audioPlayer.duration) return;

  const pct = audioPlayer.currentTime / audioPlayer.duration;
  const cutoff = Math.floor(pct * waveformBars.length);

  waveformBars.forEach((bar, i) => {
    if (i < cutoff) {
      bar.classList.add("past");
      bar.classList.remove("active");
    } else if (i === cutoff) {
      bar.classList.add("active");
      bar.classList.remove("past");
    } else {
      bar.classList.remove("past", "active");
    }
  });
});
// Reset button when finished
audioPlayer.addEventListener("ended", () => {
  audioPlayPause.textContent = "▶";
});

audioPlayPause.addEventListener("click", () => {
  if (!audioPlayer.src) return; // no audio yet

  if (audioPlayer.paused) {
    audioPlayer.play();
    audioPlayPause.textContent = "⏸";
  } else {
    audioPlayer.pause();
    audioPlayPause.textContent = "▶";
  }
});

audioWaveform.addEventListener("click", (e) => {
  if (!audioPlayer.duration) return;

  const rect = audioWaveform.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const pct = x / rect.width;

  audioPlayer.currentTime = pct * audioPlayer.duration;
});

function generateWaveformBars(count = 50) {
  audioWaveform.innerHTML = "";
  waveformBars = [];

  for (let i = 0; i < count; i++) {
    const bar = document.createElement("div");
    bar.classList.add("waveform-bar");

    // random height 10–100%
    const h = Math.random() * 70 + 30;
    bar.style.height = `${h}%`;

    audioWaveform.appendChild(bar);
    waveformBars.push(bar);
  }
}

audioPlayer.addEventListener("loadedmetadata", () => {
  generateWaveformBars(60); // 60 bars = good density
});

audioDownload.addEventListener("click", async (e) => {
  e.preventDefault();

  const url = audioDownload.href;
  if (!url || url === "#") return;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch audio");

    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = audioDownload.download || "podcast.mp3";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(objectUrl);
  } catch (err) {
    console.error("Download failed:", err);
    statusText.textContent = "Could not download audio.";
    statusText.classList.add("error-text");
  }
});

// --- Cancel Button --------------------------------------------------------

cancelBtn.addEventListener("click", async () => {
  // Nothing to cancel
  if (!currentAbortController || !currentTaskId) {
    return;
  }

  const sure = confirm("Are you sure you want to cancel generation?");
  if (!sure) return;

  // 1) Tell backend to mark this task as cancelled
  try {
    await fetch(`http://127.0.0.1:8000/api/tasks/${currentTaskId}/cancel`, {
      method: "POST",
    });
    console.log("Sent cancel for task:", currentTaskId);
  } catch (e) {
    console.warn("Cancel API error (ignored):", e);
  }


  // 2) Abort the fetch on frontend
  currentAbortController.abort();

  // 3) Reset state
  currentAbortController = null;
  currentTaskId = null;

  // 4) Reset UI
  loadingIndicator.classList.add("hidden");
  cancelBtn.classList.add("hidden");
  generateBtn.disabled = false;
  generateBtn.textContent = "Generate podcast";

  if (statusPollInterval) {
  clearInterval(statusPollInterval);
  statusPollInterval = null;
  }

  markProgressCancelled();

  statusText.textContent = "Generation cancelled.";
  statusText.classList.remove("error-text");
});

// --- Queue tracker --------------------------------------------------------

function formatStatus(stage, queuePosition) {
  const base = STATUS_LABELS[stage] || ("Stage: " + stage);

  // If no queue info (single task), just return base
  if (queuePosition == null || queuePosition < 0) {
    return base;
  }

  // Human-readable position (1-based)
  const humanPos = queuePosition + 1;

  if (queuePosition === 0) {
    return `${base}`;
  }
  return `${base} (position in queue: ${humanPos})`;
}

// --- Progress stepper -----------------------------------------------------

function updateProgressStepper(stage) {
  // reset classes
  progressSteps.forEach(step => {
    step.classList.remove("active", "done", "pending", "cancelled");
    const statusSpan = step.querySelector(".step-status");
    if (statusSpan) statusSpan.textContent = "";
  });

  const stagesOrder = ["extracting", "summary", "flashcards", "script", "audio"];
  const idx = stagesOrder.indexOf(stage);

  progressSteps.forEach(step => {
    const stepStage = step.getAttribute("data-stage");
    const statusSpan = step.querySelector(".step-status");
    const stepIndex = stagesOrder.indexOf(stepStage);

    if (idx === -1) {
      // Unknown stage: just mark all pending
      step.classList.add("pending");
      if (statusSpan) statusSpan.textContent = "Pending";
    } else if (stepIndex < idx) {
      step.classList.add("done");
      if (statusSpan) statusSpan.textContent = "Done";
    } else if (stepIndex === idx) {
      step.classList.add("active");
      if (statusSpan) statusSpan.textContent = "In progress";
    } else {
      step.classList.add("pending");
      if (statusSpan) statusSpan.textContent = "Pending";
    }
  });
}

function resetProgressStepper() {
  progressSteps.forEach(step => {
    step.classList.remove("active", "done", "pending", "cancelled");
    const statusSpan = step.querySelector(".step-status");
    if (statusSpan) statusSpan.textContent = "";
  });
}

function markProgressCancelled() {
  progressSteps.forEach(step => {
    step.classList.remove("active", "done", "pending");
    step.classList.add("cancelled");
    const statusSpan = step.querySelector(".step-status");
    if (statusSpan) statusSpan.textContent = "Cancelled";
  });
}

// --- Generate click -------------------------------------------------------

generateBtn.addEventListener("click", async () => {
  // don't allow spamming while one is running
  if (currentAbortController) return;

  const file = fileInput.files?.[0] || null;
  const text = (textInput.value || "").trim();

  if (!file && !text) {
    statusText.textContent = "Provide a PDF or some text first.";
    statusText.classList.add("error-text");
    return;
  } else {
    statusText.classList.remove("error-text");
  }

  // --- task id ---
  currentTaskId =
    (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  console.log("Starting task:", currentTaskId);

  statusText.textContent = "Queued…";
  statusText.classList.remove("error-text");
  resetProgressStepper();
  updateProgressStepper("extracting"); // or "queued" if you added that step


  // --- abort controller ---
  currentAbortController = new AbortController();
  const signal = currentAbortController.signal;

  // --- UI: generating state ---
  generateBtn.disabled = true;
  generateBtn.textContent = "Generating…";
  loadingIndicator.classList.remove("hidden");
  cancelBtn.classList.remove("hidden");
  statusText.textContent = "Sending content to backend…";
  statusText.classList.remove("error-text");

  const duration = durationSelect.value;
  const style = styleSelect.value;
  const llmProvider = llmProviderSelect.value || "";
  const llmModel = llmModelSelect.value || "";
  const ttsProvider = ttsProviderSelect.value || "";

  const formData = new FormData();
  if (file) formData.append("file", file);
  formData.append("text", text);
  formData.append("duration", duration);
  formData.append("style", style);
  formData.append("llm_provider", llmProvider);
  formData.append("llm_model", llmModel);
  formData.append("tts_provider", ttsProvider);
  formData.append("task_id", currentTaskId);

  // stepper

  resetProgressStepper();
  updateProgressStepper("extracting"); // initial stage guess

  if (statusPollInterval) {
    clearInterval(statusPollInterval);
  }
  statusPollInterval = setInterval(async () => {
  if (!currentTaskId) return;

  try {
    const res = await fetch(`http://127.0.0.1:8000/api/task_status/${currentTaskId}`);
    if (!res.ok) return;

    const data = await res.json();
    const stage = data.stage;

    if (stage) {
      updateProgressStepper(stage);

      const queuePosition = data.queuePosition;
      const label = formatStatus(stage, queuePosition);
      statusText.textContent = label;

      if (stage === "done") {
        statusText.classList.remove("error-text");
      } else if (stage === "error") {
        statusText.classList.add("error-text");
      }
    }
  } catch (e) {
    // Ignore polling errors
  }
  }, 5000);


  // debug
  console.log("FormData being sent:");
  for (const [k, v] of formData.entries()) {
    console.log("  ", k, "=", v);
  }

  try {
    const res = await fetch("http://127.0.0.1:8000/api/process", {
      method: "POST",
      body: formData,
      signal,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `Request failed with ${res.status}`);
    }

    const data = await res.json();
    console.log("Response:", data);

    // --- Summary ---
    summaryContent.classList.remove("placeholder");
    summaryContent.textContent = data.summary || "(No summary received.)";

    // --- Script ---
    scriptContent.classList.remove("placeholder");
    scriptContent.innerHTML = `<pre>${data.script || "(No script received.)"}</pre>`;

    // --- Flashcards ---
    flashcardsContent.classList.remove("placeholder");
    if (Array.isArray(data.flashcards) && data.flashcards.length > 0) {
      flashcardsContent.innerHTML = `
        <ul class="flashcard-list">
          ${data.flashcards
            .map(
              (fc, idx) => `
              <li class="flashcard-item">
                <div class="flashcard-question">Q${idx + 1}: ${fc.question || ""}</div>
                <div class="flashcard-answer">${fc.answer || ""}</div>
              </li>
            `
            )
            .join("")}
        </ul>
      `;
    } else {
      flashcardsContent.textContent = "No flashcards generated.";
    }

    // --- Audio ---
    if (data.audioUrl) {
      const url = "http://127.0.0.1:8000" + data.audioUrl;

      audioPlaceholder.classList.add("hidden");
      audioPlayerShell.classList.remove("hidden");

      audioPlayer.src = url;
      audioDownload.href = url;

      audioPlayPause.textContent = "▶";
      audioCurrentEl.textContent = "0:00";
      audioProgressFill.style.width = "0%";
    } else {
      audioPlayerShell.classList.add("hidden");
      audioPlaceholder.classList.remove("hidden");
      audioPlaceholder.textContent =
        "No audio generated (TTS disabled or failed).";
    }

    statusText.textContent = "Done. Script and flashcards are ready.";
    statusText.classList.remove("error-text");
  } catch (err) {
    if (err.name === "AbortError") {
      console.log("Generation aborted by user.");
      statusText.textContent = "Generation cancelled.";
      statusText.classList.remove("error-text");
    } else {
      console.error(err);
      statusText.textContent = "Backend error: " + err.message;
      statusText.classList.add("error-text");
    }
  } finally {
    // reset state
    currentAbortController = null;
    currentTaskId = null;

    generateBtn.disabled = false;
    generateBtn.textContent = "Generate podcast";
    loadingIndicator.classList.add("hidden");
    cancelBtn.classList.add("hidden");
  }
});