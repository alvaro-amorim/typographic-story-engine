"use strict";

const state = {
  capabilities: null,
  currentJobId: null,
  pollTimer: null,
};

const elements = {
  form: document.querySelector("#generation-form"),
  prompt: document.querySelector("#prompt"),
  promptCount: document.querySelector("#prompt-count"),
  preset: document.querySelector("#preset"),
  presetDescription: document.querySelector("#preset-description"),
  provider: document.querySelector("#provider"),
  ollamaFields: document.querySelector("#ollama-fields"),
  ollamaModel: document.querySelector("#ollama-model"),
  ollamaUrl: document.querySelector("#ollama-url"),
  duration: document.querySelector("#duration"),
  fps: document.querySelector("#fps"),
  movement: document.querySelector("#movement"),
  generateVideo: document.querySelector("#generate-video"),
  generateButton: document.querySelector("#generate-button"),
  apiStatus: document.querySelector("#api-status"),
  registryStatus: document.querySelector("#registry-status"),
  ffmpegStatus: document.querySelector("#ffmpeg-status"),
  emptyResult: document.querySelector("#empty-result"),
  activeResult: document.querySelector("#active-result"),
  resultTitle: document.querySelector("#result-title"),
  jobStatus: document.querySelector("#job-status"),
  progressBar: document.querySelector("#progress-bar"),
  progressValue: document.querySelector("#progress-value"),
  stageLabel: document.querySelector("#stage-label"),
  errorMessage: document.querySelector("#error-message"),
  videoPlayer: document.querySelector("#video-player"),
  previewImage: document.querySelector("#preview-image"),
  jobMetadata: document.querySelector("#job-metadata"),
  artifactList: document.querySelector("#artifact-list"),
  historyList: document.querySelector("#history-list"),
  refreshHistory: document.querySelector("#refresh-history"),
};

const stageLabels = {
  queued: "Na fila",
  starting: "Iniciando",
  loading_registry: "Carregando catálogo de assets",
  planning: "Interpretando o prompt",
  preparing_animation: "Preparando animação",
  generating_frames: "Gerando frames tipográficos",
  exporting_video: "Exportando MP4",
  completed: "Concluído",
  failed: "Falhou",
  interrupted: "Interrompido",
};

function setPill(element, text, variant) {
  element.textContent = text;
  element.className = `pill ${variant}`;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;
  if (!response.ok) {
    const detail = payload && payload.detail ? payload.detail : `${response.status} ${response.statusText}`;
    throw new Error(detail);
  }
  return payload;
}

function updatePromptCount() {
  elements.promptCount.textContent = `${elements.prompt.value.length} / 4000`;
  localStorage.setItem("tse-studio-prompt", elements.prompt.value);
}

function updateProviderFields() {
  elements.ollamaFields.classList.toggle("hidden", elements.provider.value !== "ollama");
  localStorage.setItem("tse-studio-provider", elements.provider.value);
}

function updatePresetDescription() {
  const config = state.capabilities?.presets?.[elements.preset.value];
  if (!config) return;
  elements.presetDescription.textContent = `${config.description} ${config.duration_seconds}s · ${config.fps} FPS`;
  elements.duration.placeholder = String(config.duration_seconds);
  elements.fps.placeholder = String(config.fps);
  localStorage.setItem("tse-studio-preset", elements.preset.value);
}

function restoreForm() {
  const prompt = localStorage.getItem("tse-studio-prompt");
  const provider = localStorage.getItem("tse-studio-provider");
  const preset = localStorage.getItem("tse-studio-preset");
  if (prompt) elements.prompt.value = prompt;
  if (provider && ["deterministic", "ollama"].includes(provider)) {
    elements.provider.value = provider;
  }
  if (preset && ["draft", "standard", "quality"].includes(preset)) {
    elements.preset.value = preset;
  }
  updatePromptCount();
  updateProviderFields();
}

async function loadCapabilities() {
  try {
    const capabilities = await requestJson("/v1/capabilities");
    state.capabilities = capabilities;
    setPill(elements.apiStatus, `API ${capabilities.version}`, "ok");
    setPill(
      elements.registryStatus,
      capabilities.default_registry_ready ? "Assets prontos" : "Assets indisponíveis",
      capabilities.default_registry_ready ? "ok" : "error",
    );
    setPill(
      elements.ffmpegStatus,
      capabilities.ffmpeg_available ? "FFmpeg pronto" : "FFmpeg ausente",
      capabilities.ffmpeg_available ? "ok" : "warn",
    );
    if (!capabilities.ffmpeg_available) {
      elements.generateVideo.checked = false;
    }
    elements.generateButton.disabled = !capabilities.default_registry_ready;
    updatePresetDescription();
  } catch (error) {
    setPill(elements.apiStatus, "API indisponível", "error");
    elements.generateButton.disabled = true;
    showClientError(error.message);
  }
}

function showClientError(message) {
  elements.emptyResult.classList.add("hidden");
  elements.activeResult.classList.remove("hidden");
  elements.errorMessage.textContent = message;
  elements.errorMessage.classList.remove("hidden");
  elements.resultTitle.textContent = "Não foi possível iniciar";
  elements.jobStatus.textContent = "Erro";
  elements.jobStatus.className = "status-badge failed";
}

function numberOrNull(input) {
  if (!input.value.trim()) return null;
  const value = Number(input.value);
  return Number.isFinite(value) ? value : null;
}

async function submitGeneration(event) {
  event.preventDefault();
  elements.errorMessage.classList.add("hidden");
  elements.generateButton.disabled = true;
  elements.generateButton.textContent = "Enviando...";

  const payload = {
    prompt: elements.prompt.value,
    provider: elements.provider.value,
    preset: elements.preset.value,
    ollama_model: elements.ollamaModel.value,
    ollama_url: elements.ollamaUrl.value,
    duration_seconds: numberOrNull(elements.duration),
    fps: numberOrNull(elements.fps),
    movement_fraction: Number(elements.movement.value),
    generate_video: elements.generateVideo.checked,
  };

  try {
    const created = await requestJson("/v1/generations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.currentJobId = created.id;
    const url = new URL(window.location.href);
    url.searchParams.set("job", created.id);
    history.replaceState({}, "", url);
    await loadJob(created.id);
    await loadHistory();
  } catch (error) {
    showClientError(error.message);
  } finally {
    elements.generateButton.disabled = !(state.capabilities?.default_registry_ready);
    elements.generateButton.textContent = "Gerar vídeo";
  }
}

function metadataCard(label, value) {
  const card = document.createElement("div");
  card.className = "metadata-card";
  const strong = document.createElement("strong");
  strong.textContent = label;
  const span = document.createElement("span");
  span.textContent = value ?? "—";
  card.append(strong, span);
  return card;
}

function artifactUrl(jobId, artifact) {
  const encoded = artifact.split("/").map(encodeURIComponent).join("/");
  return `/v1/jobs/${encodeURIComponent(jobId)}/artifacts/${encoded}`;
}

function renderArtifacts(job) {
  elements.artifactList.replaceChildren();
  const preferred = job.artifacts.filter((item) =>
    item.endsWith(".mp4") || item.endsWith("_validation.json") || item.endsWith("_manifest.json") || item.endsWith("_plan.json")
  );
  const artifacts = preferred.length ? preferred : job.artifacts.slice(0, 12);
  if (!artifacts.length) {
    const empty = document.createElement("span");
    empty.className = "muted";
    empty.textContent = "Os artefatos aparecerão após a geração.";
    elements.artifactList.append(empty);
    return;
  }
  artifacts.forEach((artifact) => {
    const link = document.createElement("a");
    link.href = artifactUrl(job.id, artifact);
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = artifact;
    link.title = artifact;
    elements.artifactList.append(link);
  });
}

function renderJob(job) {
  state.currentJobId = job.id;
  elements.emptyResult.classList.add("hidden");
  elements.activeResult.classList.remove("hidden");
  elements.resultTitle.textContent = job.request.story;
  elements.jobStatus.textContent = job.status;
  elements.jobStatus.className = `status-badge ${job.status}`;

  const percentage = Math.max(0, Math.min(100, Math.round(job.progress * 100)));
  elements.progressBar.style.width = `${percentage}%`;
  elements.progressValue.textContent = `${percentage}%`;
  elements.stageLabel.textContent = stageLabels[job.stage] || job.stage;

  elements.errorMessage.classList.toggle("hidden", !job.error);
  elements.errorMessage.textContent = job.error || "";

  elements.jobMetadata.replaceChildren(
    metadataCard("Job", job.id.slice(0, 10)),
    metadataCard("Provider", job.planner_provider || job.request.provider),
    metadataCard("Frames", job.frame_count == null ? "—" : String(job.frame_count)),
    metadataCard("Duração", `${job.request.duration_seconds}s`),
  );
  renderArtifacts(job);

  elements.videoPlayer.classList.add("hidden");
  elements.previewImage.classList.add("hidden");
  if (job.status === "completed" && job.video_path) {
    const source = `/v1/jobs/${encodeURIComponent(job.id)}/video?v=${encodeURIComponent(job.updated_at)}`;
    if (elements.videoPlayer.dataset.jobId !== job.id) {
      elements.videoPlayer.src = source;
      elements.videoPlayer.dataset.jobId = job.id;
      elements.videoPlayer.load();
    }
    elements.videoPlayer.classList.remove("hidden");
  } else if (job.status === "completed" && job.artifacts.some((item) => item.endsWith(".png"))) {
    elements.previewImage.src = `/v1/jobs/${encodeURIComponent(job.id)}/preview?v=${encodeURIComponent(job.updated_at)}`;
    elements.previewImage.classList.remove("hidden");
  }
}

async function loadJob(jobId) {
  clearTimeout(state.pollTimer);
  try {
    const job = await requestJson(`/v1/jobs/${encodeURIComponent(jobId)}`);
    renderJob(job);
    if (["queued", "running"].includes(job.status)) {
      state.pollTimer = setTimeout(() => loadJob(jobId), 900);
    } else {
      await loadHistory();
    }
  } catch (error) {
    showClientError(error.message);
  }
}

function historyItem(job) {
  const item = document.createElement("article");
  item.className = "history-item";

  const main = document.createElement("div");
  main.className = "history-main";
  const prompt = document.createElement("p");
  prompt.className = "history-prompt";
  prompt.textContent = job.request.story;
  const meta = document.createElement("p");
  meta.className = "history-meta";
  meta.textContent = `${job.status} · ${Math.round(job.progress * 100)}% · ${new Date(job.created_at).toLocaleString("pt-BR")}`;
  main.append(prompt, meta);

  const actions = document.createElement("div");
  actions.className = "history-actions";
  const open = document.createElement("button");
  open.type = "button";
  open.className = "history-open";
  open.textContent = job.video_path ? "Assistir" : "Abrir";
  open.addEventListener("click", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("job", job.id);
    history.replaceState({}, "", url);
    loadJob(job.id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "danger-button";
  remove.textContent = "Excluir";
  remove.addEventListener("click", async () => {
    if (!window.confirm("Excluir este job e todos os seus artefatos?")) return;
    await fetch(`/v1/jobs/${encodeURIComponent(job.id)}`, { method: "DELETE" });
    if (state.currentJobId === job.id) {
      state.currentJobId = null;
      elements.activeResult.classList.add("hidden");
      elements.emptyResult.classList.remove("hidden");
      elements.resultTitle.textContent = "Nenhuma geração iniciada";
      elements.jobStatus.textContent = "Aguardando";
      elements.jobStatus.className = "status-badge idle";
      const url = new URL(window.location.href);
      url.searchParams.delete("job");
      history.replaceState({}, "", url);
    }
    await loadHistory();
  });

  actions.append(open, remove);
  item.append(main, actions);
  return item;
}

async function loadHistory() {
  try {
    const jobs = await requestJson("/v1/jobs");
    elements.historyList.replaceChildren();
    if (!jobs.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Nenhuma geração registrada.";
      elements.historyList.append(empty);
      return;
    }
    jobs.slice(0, 20).forEach((job) => elements.historyList.append(historyItem(job)));
  } catch (error) {
    elements.historyList.textContent = `Falha ao carregar histórico: ${error.message}`;
  }
}

async function initialize() {
  restoreForm();
  await loadCapabilities();
  await loadHistory();
  const jobId = new URLSearchParams(window.location.search).get("job");
  if (jobId) await loadJob(jobId);
}

elements.form.addEventListener("submit", submitGeneration);
elements.prompt.addEventListener("input", updatePromptCount);
elements.provider.addEventListener("change", updateProviderFields);
elements.preset.addEventListener("change", updatePresetDescription);
elements.refreshHistory.addEventListener("click", loadHistory);

initialize();
