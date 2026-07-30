from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from pydantic import ValidationError

from engine.models import Glyph
from engine.scene_models import SceneObjectSpec, SceneObjectState, SceneSpec, SceneState

FORBIDDEN_VISIBLE_TAGS = (
    "<path",
    "<rect",
    "<circle",
    "<ellipse",
    "<polygon",
    "<polyline",
    "<line",
    "<image",
    "<use",
)

LAYER_ORDER = {"texture": 0, "fill": 1, "outline": 2}
STYLE_ROLE_ORDER = {
    "texture_accent": 0,
    "fill_mass": 1,
    "outline_shadow": 2,
    "outline_detail": 3,
}


@dataclass(frozen=True)
class LoadedSceneObject:
    spec: SceneObjectSpec
    glyphs: tuple[Glyph, ...]
    resolved_path: Path


def load_scene_spec(path: str | Path) -> SceneSpec:
    scene_path = Path(path)
    try:
        payload = json.loads(scene_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid scene JSON: {error}") from error
    return SceneSpec.model_validate(payload)


def resolve_scene_paths(scene: SceneSpec, scene_path: str | Path) -> SceneSpec:
    """Resolve relative glyph-state paths against the scene JSON directory."""
    base_directory = Path(scene_path).resolve().parent
    resolved_objects = []
    for item in scene.objects:
        glyphs_path = item.glyphs_path
        if not glyphs_path.is_absolute():
            glyphs_path = (base_directory / glyphs_path).resolve()
        resolved_objects.append(item.model_copy(update={"glyphs_path": glyphs_path}))
    return scene.model_copy(update={"objects": resolved_objects})


def load_object_glyphs(spec: SceneObjectSpec) -> LoadedSceneObject:
    path = spec.glyphs_path
    if not path.is_file():
        raise ValueError(f"glyph-state file not found for object '{spec.id}': {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid glyph JSON for object '{spec.id}': {error}") from error

    if not isinstance(payload, list) or not payload:
        raise ValueError(
            f"glyph-state for object '{spec.id}' must be a non-empty JSON list"
        )

    glyphs: list[Glyph] = []
    try:
        for index, raw_glyph in enumerate(payload):
            source = Glyph.model_validate(raw_glyph)
            glyphs.append(
                source.model_copy(
                    update={
                        "id": f"{spec.id}::{source.id or index}",
                        "object_id": spec.id,
                    }
                )
            )
    except ValidationError as error:
        raise ValueError(f"invalid glyph state for object '{spec.id}': {error}") from error

    return LoadedSceneObject(spec=spec, glyphs=tuple(glyphs), resolved_path=path)


def load_scene_objects(scene: SceneSpec) -> list[LoadedSceneObject]:
    loaded = [load_object_glyphs(item) for item in scene.objects]
    return sorted(loaded, key=lambda item: (item.spec.z_index, item.spec.id))


def _transform_attribute(spec: SceneObjectSpec) -> str:
    transform = spec.transform
    parts = [f"translate({transform.x:.3f} {transform.y:.3f})"]
    if transform.rotation != 0.0:
        parts.append(f"rotate({transform.rotation:.3f})")
    if transform.scale_x != 1.0 or transform.scale_y != 1.0:
        parts.append(f"scale({transform.scale_x:.6f} {transform.scale_y:.6f})")
    return " ".join(parts)


def _render_glyph(glyph: Glyph) -> str:
    transform = f"translate({glyph.x:.3f} {glyph.y:.3f})"
    if glyph.rotation != 0.0:
        transform += f" rotate({glyph.rotation:.3f})"

    return (
        f'<text x="0" y="0" font-size="{glyph.font_size:.3f}" '
        f'opacity="{glyph.opacity:.3f}" transform="{transform}" '
        f'font-family="monospace" text-anchor="middle" dominant-baseline="central" '
        f'fill="{escape(glyph.color, quote=True)}" '
        f'data-glyph-id="{escape(glyph.id, quote=True)}" '
        f'data-object-id="{escape(glyph.object_id, quote=True)}" '
        f'data-layer="{escape(glyph.layer, quote=True)}" '
        f'data-zone="{escape(glyph.zone, quote=True)}" '
        f'data-style-role="{escape(glyph.style_role, quote=True)}">'
        f'{escape(glyph.character)}</text>'
    )


def _ordered_glyphs(glyphs: Iterable[Glyph]) -> list[Glyph]:
    return sorted(
        glyphs,
        key=lambda glyph: (
            LAYER_ORDER.get(glyph.layer, len(LAYER_ORDER)),
            STYLE_ROLE_ORDER.get(glyph.style_role, len(STYLE_ROLE_ORDER)),
            -glyph.font_size,
            glyph.id,
        ),
    )


def render_scene_svg(scene: SceneSpec, objects: Sequence[LoadedSceneObject]) -> str:
    """Render a text-only scene while preserving one independent group per object."""
    root_style = ""
    if scene.background != "transparent":
        root_style = f' style="background-color:{escape(scene.background, quote=True)}"'

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" '
        f'height="{scene.height}" viewBox="0 0 {scene.width} {scene.height}"{root_style}>',
        f'  <g id="scene_{escape(scene.id, quote=True)}" '
        f'data-scene-id="{escape(scene.id, quote=True)}">',
    ]

    for loaded in objects:
        spec = loaded.spec
        if not spec.visible:
            continue
        lines.append(
            f'    <g id="object_{escape(spec.id, quote=True)}" '
            f'data-object-id="{escape(spec.id, quote=True)}" '
            f'data-word="{escape(spec.word, quote=True)}" '
            f'data-z-index="{spec.z_index}" opacity="{spec.transform.opacity:.3f}" '
            f'transform="{_transform_attribute(spec)}">'
        )

        ordered = _ordered_glyphs(loaded.glyphs)
        current_layer: str | None = None
        current_role: str | None = None
        for glyph in ordered:
            if glyph.layer != current_layer:
                if current_role is not None:
                    lines.append("        </g>")
                    current_role = None
                if current_layer is not None:
                    lines.append("      </g>")
                current_layer = glyph.layer
                lines.append(
                    f'      <g id="{escape(spec.id, quote=True)}_layer_'
                    f'{escape(current_layer, quote=True)}" '
                    f'data-layer="{escape(current_layer, quote=True)}">'
                )

            if glyph.style_role != current_role:
                if current_role is not None:
                    lines.append("        </g>")
                current_role = glyph.style_role
                lines.append(
                    f'        <g id="{escape(spec.id, quote=True)}_role_'
                    f'{escape(current_role, quote=True)}" '
                    f'data-style-role="{escape(current_role, quote=True)}">'
                )

            lines.append("          " + _render_glyph(glyph))

        if current_role is not None:
            lines.append("        </g>")
        if current_layer is not None:
            lines.append("      </g>")
        lines.append("    </g>")

    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


def build_scene_state(scene: SceneSpec, objects: Sequence[LoadedSceneObject]) -> SceneState:
    return SceneState(
        id=scene.id,
        width=scene.width,
        height=scene.height,
        background=scene.background,
        objects=[
            SceneObjectState(
                id=item.spec.id,
                word=item.spec.word,
                source_glyphs_path=str(item.resolved_path),
                source_glyph_count=len(item.glyphs),
                z_index=item.spec.z_index,
                visible=item.spec.visible,
                transform=item.spec.transform,
            )
            for item in objects
        ],
    )


def validate_composed_scene(
    scene: SceneSpec,
    objects: Sequence[LoadedSceneObject],
    svg_output: str,
) -> dict[str, object]:
    object_reports: dict[str, dict[str, object]] = {}
    all_glyph_ids: list[str] = []

    for loaded in objects:
        allowed = loaded.spec.allowed_characters
        invalid = [
            glyph.id for glyph in loaded.glyphs if glyph.character.upper() not in allowed
        ]
        all_glyph_ids.extend(glyph.id for glyph in loaded.glyphs)
        object_reports[loaded.spec.id] = {
            "word": loaded.spec.word,
            "glyph_count": len(loaded.glyphs),
            "allowed_characters": sorted(allowed),
            "invalid_glyph_ids": invalid,
            "semantic_characters_respected": not invalid,
            "z_index": loaded.spec.z_index,
        }

    id_counts = Counter(all_glyph_ids)
    duplicate_glyph_ids = sorted(
        identifier for identifier, count in id_counts.items() if count > 1
    )
    svg_lower = svg_output.lower()
    forbidden_tags = [tag for tag in FORBIDDEN_VISIBLE_TAGS if tag in svg_lower]
    missing_object_groups = [
        item.spec.id
        for item in objects
        if item.spec.visible and f'id="object_{item.spec.id}"' not in svg_output
    ]

    semantic_valid = all(
        bool(report["semantic_characters_respected"])
        for report in object_reports.values()
    )
    strict_valid = not forbidden_tags
    is_valid = (
        semantic_valid
        and strict_valid
        and not duplicate_glyph_ids
        and not missing_object_groups
    )

    return {
        "is_valid": is_valid,
        "scene_id": scene.id,
        "strict_mode_respected": strict_valid,
        "semantic_characters_respected": semantic_valid,
        "forbidden_tags_found": forbidden_tags,
        "duplicate_glyph_ids": duplicate_glyph_ids,
        "missing_object_groups": missing_object_groups,
        "object_order": [item.spec.id for item in objects],
        "visible_object_count": sum(1 for item in objects if item.spec.visible),
        "total_object_count": len(objects),
        "total_glyph_count": sum(len(item.glyphs) for item in objects),
        "objects": object_reports,
    }
