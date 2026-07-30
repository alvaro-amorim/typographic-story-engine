# Asset Registry and Deterministic Story Planner

The story planner is the first orchestration layer above the renderer, scene composer, animator and video exporter.

It does not generate artwork directly. It selects existing semantic assets and produces two compatible Scene Graphs plus one animation specification.

## Asset Registry

```json
{
  "id": "cat_moon_ground",
  "width": 1280,
  "height": 720,
  "background": "#F5F1E8",
  "assets": [
    {
      "id": "cat_01",
      "word": "CAT",
      "glyphs_path": "objects/cat/cat_01_scene.json",
      "aliases": ["cat", "gato"],
      "tags": ["subject", "animal"],
      "z_index": 3,
      "transform": {
        "x": 390,
        "y": 255,
        "scale_x": 0.88,
        "scale_y": 0.88,
        "rotation": 2
      }
    }
  ]
}
```

Each asset stores:

- stable object ID;
- semantic word;
- pre-rendered glyph-state JSON;
- aliases used to match story text;
- tags such as `subject`, `environment` and `celestial`;
- default `z_index`;
- default scene transform;
- optional `always_include` behavior.

Relative glyph paths are resolved from the registry location.

## Planner CLI

```powershell
python plan_story.py `
  --story "A cat looks at the moon and then walks away." `
  --registry outputs/assets/asset_registry.json `
  --id cat_story_01 `
  --duration 2 `
  --fps 12 `
  --output-dir outputs/story-plans
```

The planner writes:

```text
outputs/story-plans/cat_story_01/
├── cat_story_01_plan.json
├── cat_story_01_scene_001.json
├── cat_story_01_scene_002.json
└── cat_story_01_animation.json
```

The animation file can be passed directly to:

```powershell
python animate_scenes.py `
  --animation outputs/story-plans/cat_story_01/cat_story_01_animation.json `
  --output-dir outputs/animations
```

## Supported deterministic intent

The MVP identifies:

- subject through aliases and the `subject` tag;
- movement to the left;
- movement to the right;
- generic movement, defaulting to the right;
- a pose transition when no movement is found;
- fade behavior later through scene visibility.

English and Portuguese aliases are supported through accent-insensitive normalization.

Examples:

```text
A cat looks at the moon and walks away.
O gato olha para a lua e caminha para a esquerda.
A cat watches the moon.
```

## Determinism

For the same story, registry and options, the planner produces:

- the same story ID when none is supplied;
- the same selected assets;
- the same template;
- the same transforms;
- the same scene and animation JSON.

The planner does not modify glyph coordinates.

## Complete story-to-video demo

Without FFmpeg:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 1 `
  --fps 4 `
  --skip-video
```

With FFmpeg installed:

```powershell
python -m examples.build_story_video_demo `
  --story "A cat looks at the moon and then walks away." `
  --duration 2 `
  --fps 12 `
  --preset fast
```

Output:

```text
outputs/demo-story-video/cat_story_01.mp4
```

## Architectural boundary

A future LLM planner will replace only the deterministic interpretation step.

The following contracts remain unchanged:

```text
Story
  -> Asset IDs
  -> Scene Graphs
  -> Animation specification
  -> SVG/PNG frames
  -> MP4
```

This keeps AI providers optional and prevents them from generating uncontrolled SVG code.

## Next step

The next stage is a provider interface with:

- deterministic planner for tests and offline operation;
- Ollama provider for local natural-language planning;
- schema validation and fallback to the deterministic planner.
