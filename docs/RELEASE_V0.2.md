# Release v0.2 — End-to-end vertical slice

This release moves the project from an isolated typographic renderer to a complete local story pipeline.

## Included

### Multi-object scenes

- persistent object IDs;
- independent semantic words;
- group-level transforms;
- z-index ordering;
- per-object validation;
- strict text-only visible SVG.

### Animation

- two compatible Scene Graphs;
- transform interpolation;
- easing;
- opacity fades;
- SVG and PNG frames;
- manifests and frame validation;
- glyph reuse without regeneration.

### Video

- contiguous PNG sequence validation;
- optional FFmpeg resolution;
- H.264 MP4;
- yuv420p compatibility;
- faststart;
- CRF and preset controls.

### Story planning

- Asset Registry;
- deterministic English and Portuguese aliases;
- subject selection;
- environment inclusion;
- left, right and pose templates;
- story-to-scene manifests.

### Local AI

- Ollama `/api/chat` provider;
- Pydantic JSON Schema structured output;
- zero-temperature planning;
- known-asset validation;
- deterministic fallback;
- provider metadata in manifests.

### API

- FastAPI local service;
- background jobs;
- progress stages;
- atomic JSON persistence;
- restart interruption detection;
- artifact listing and download;
- traversal protection;
- OpenAPI documentation.

## Main vertical slice

```text
Story text
  → Planner
  → Asset Registry
  → Scene 1 + Scene 2
  → Persistent object animation
  → SVG/PNG frames
  → MP4
  → FastAPI job artifacts
```

## Demonstration

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 1 `
  --fps 6 `
  --preset fast
```

## Compatibility

The complete test suite runs on Windows with:

- Python 3.12;
- Python 3.14.

Ollama and FFmpeg remain optional external tools. The deterministic planner and SVG-only frame path work without them.

## Known limitations

- two scenes per planned story;
- small demonstration registry;
- object-level animation only;
- in-process FastAPI background tasks;
- no authentication or production database.
