# Local Ollama Story Planner

O Ollama is an optional local provider for the story decision step. It never generates SVG or glyph coordinates.

The provider returns a validated `StoryDecision` containing only:

- `subject_asset_id`;
- `included_asset_ids`;
- `movement_direction`;
- `movement_fraction`.

The deterministic engine still creates Scene Graphs, validates asset IDs and produces the animation.

## Requirements

Install Ollama and make sure its local API is available:

```powershell
ollama --version
```

Download or select a model:

```powershell
ollama pull qwen3:4b
```

The project does not require the Ollama Python package. It calls the local HTTP API directly.

## Structured output

The provider calls:

```text
POST http://localhost:11434/api/chat
```

Request behavior:

- `stream: false`;
- `format`: Pydantic JSON Schema for `StoryDecision`;
- `options.temperature: 0`;
- asset registry included in the prompt;
- instruction to select existing asset IDs only.

The response is validated again with Pydantic before any scene is created.

## Planner CLI

```powershell
python plan_story.py `
  --story "A cat looks at the moon and then walks away." `
  --registry outputs/demo-story-video/asset_registry.json `
  --provider ollama `
  --ollama-model qwen3:4b `
  --output-dir outputs/ollama-plans
```

Custom endpoint:

```powershell
python plan_story.py `
  --story "O gato olha para a lua e caminha para a esquerda." `
  --registry outputs/demo-story-video/asset_registry.json `
  --provider ollama `
  --ollama-model qwen3:4b `
  --ollama-url http://localhost:11434 `
  --ollama-timeout 90
```

## Fallback

Fallback to the deterministic planner is enabled by default when:

- Ollama is offline;
- the request times out;
- the model returns invalid JSON;
- the model invents an asset ID;
- the selected subject is not tagged `subject`;
- the decision violates the schema.

Disable fallback when testing provider quality:

```powershell
python plan_story.py `
  --story "A cat walks away from the moon." `
  --registry outputs/demo-story-video/asset_registry.json `
  --provider ollama `
  --ollama-model qwen3:4b `
  --no-fallback
```

The story plan manifest records:

```json
{
  "planner_provider": "deterministic",
  "planner_model": null,
  "planner_fallback_used": true,
  "planner_error": "ollama: ..."
}
```

## Complete local AI demo

Generate story, scenes and SVG frames without FFmpeg:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --provider ollama `
  --ollama-model qwen3:4b `
  --skip-video
```

Generate the MP4 when FFmpeg is installed:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --provider ollama `
  --ollama-model qwen3:4b `
  --duration 2 `
  --fps 12 `
  --preset fast
```

## Safety boundary

The model cannot bypass the registry because provider output is converted into `StoryDecision` and then checked against:

- known asset IDs;
- subject tags;
- required environment assets;
- existing glyph files;
- semantic word restrictions;
- persistent scene compatibility.

A valid provider response changes orchestration only. It never changes the strict typographic renderer.
