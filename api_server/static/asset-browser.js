"use strict";

function assetLabel(kind) {
  return kind === "subject" ? "Personagem" : "Cenário";
}

function appendAssetToPrompt(word) {
  const prompt = document.querySelector("#prompt");
  if (!prompt) return;
  const current = prompt.value.trim();
  const addition = word.toLowerCase();
  if (!current) {
    prompt.value = addition;
  } else if (!current.toLowerCase().includes(addition)) {
    prompt.value = `${current.replace(/[.?!]+$/, "")} with ${addition}.`;
  }
  prompt.dispatchEvent(new Event("input", { bubbles: true }));
  prompt.focus();
}

function renderAssetBrowser(capabilities) {
  const grid = document.querySelector("#asset-grid");
  const count = document.querySelector("#asset-count");
  const summary = document.querySelector("#asset-summary");
  if (!grid || !count || !summary) return;

  const assets = Array.isArray(capabilities.assets) ? capabilities.assets : [];
  grid.replaceChildren();
  count.textContent = `${assets.length} assets`;
  count.className = `pill ${assets.length ? "ok" : "warn"}`;

  const words = Array.isArray(capabilities.asset_words)
    ? capabilities.asset_words
    : assets.map((asset) => asset.word);
  summary.textContent = words.length
    ? `Palavras disponíveis: ${words.join(", ")}.`
    : "Nenhum asset disponível no registry atual.";

  if (!assets.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "O registry não forneceu assets para exibição.";
    grid.append(empty);
    return;
  }

  assets.forEach((asset) => {
    const card = document.createElement("article");
    card.className = `asset-card ${asset.kind}`;

    const header = document.createElement("div");
    header.className = "asset-card-header";
    const word = document.createElement("strong");
    word.className = "asset-word";
    word.textContent = asset.word;
    const kind = document.createElement("span");
    kind.className = "asset-kind";
    kind.textContent = assetLabel(asset.kind);
    header.append(word, kind);

    const id = document.createElement("code");
    id.className = "asset-id";
    id.textContent = asset.id;

    const aliases = document.createElement("p");
    aliases.className = "asset-aliases";
    const visibleAliases = (asset.aliases || [])
      .filter((alias) => alias.toUpperCase() !== asset.word)
      .slice(0, 6);
    aliases.textContent = visibleAliases.length
      ? `Aliases: ${visibleAliases.join(", ")}`
      : "Sem aliases adicionais";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "asset-use-button";
    button.textContent = "Adicionar ao prompt";
    button.addEventListener("click", () => appendAssetToPrompt(asset.word));

    card.append(header, id, aliases, button);
    grid.append(card);
  });
}

async function loadAssetBrowser() {
  try {
    const response = await fetch("/v1/capabilities");
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    renderAssetBrowser(await response.json());
  } catch (error) {
    const count = document.querySelector("#asset-count");
    const summary = document.querySelector("#asset-summary");
    if (count) {
      count.textContent = "Indisponível";
      count.className = "pill error";
    }
    if (summary) summary.textContent = `Falha ao carregar catálogo: ${error.message}`;
  }
}

window.addEventListener("DOMContentLoaded", loadAssetBrowser);
