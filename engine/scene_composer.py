from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

from engine.balanced_styling import BalancedStyleConfig, distribute_balanced_glyphs
from engine.glyph_distribution import DistributionConfig, OrientationConfig
from engine.image_analysis import analyze_mask
from engine.models import Glyph, SemanticObject
from engine.scene_models import SceneDefinition, SceneObject
from engine.semantic_validation import FORBIDDEN_TAGS, validate_scene
from engine.svg_renderer import render_glyph_groups


@dataclass(frozen=True)
class RenderedSceneObject:
    definition: SceneObject
    glyphs: tuple[Glyph, ...]
    mask_width: int
    mask_height: int
    resolved_mask_path: str


@dataclass(frozen=True)
class RenderedScene:
    definition: SceneDefinition
    objects: tuple[RenderedSceneObject, ...]

    @property
    def glyphs(self) -> tuple[Glyph, ...]:
        return tuple(glyph for item in self.objects for glyph in item.glyphs)


def render_scene_object(
    definition: SceneObject,
    *,
    base_dir: Path,
    distribution_config: DistributionConfig | None = None,
    orientation_config: OrientationConfig | None = None,
    style_config: BalancedStyleConfig | None = None,
    orientation_smoothing: float = 2.0,
) -> RenderedSceneObject:
    """Render one semantic object in local mask coordinates."""
    mask_path = definition.resolve_mask_path(base_dir).resolve()
    if not mask_path.is_file():
        raise ValueError(
            f"mask for object '{definition.id}' was not found: {mask_path}"
        )

    semantic_object = SemanticObject(
        id=definition.id,
        word=definition.word,
        mask_path=str(mask_path),
        glyph_count=definition.glyph_count,
        font_size_range=definition.font_size_range,
        palette=definition.palette,
        seed=definition.seed,
    )
    distribution = distribution_config or DistributionConfig()
    orientation = orientation_config or OrientationConfig()
    style = style_config or BalancedStyleConfig()
    analysis = analyze_mask(
        semantic_object.mask_path,
        orientation_smoothing=orientation_smoothing,
    )
    glyphs = distribute_balanced_glyphs(
        object_id=semantic_object.id,
        valid_coords=analysis.valid_coordinates,
        character_sequence=semantic_object.character_sequence,
        glyph_count=semantic_object.glyph_count,
        font_size_range=semantic_object.font_size_range,
        palette=semantic_object.palette,
        seed=semantic_object.seed,
        distribution_config=distribution,
        orientation_field=analysis.tangent_field if orientation.enabled else None,
        orientation_config=orientation,
        style_config=style,
    )
    return RenderedSceneObject(
        definition=definition,
        glyphs=tuple(glyphs),
        mask_width=analysis.width,
        mask_height=analysis.height,
        resolved_mask_path=str(mask_path),
    )


def render_scene(
    definition: SceneDefinition,
    *,
    base_dir: Path,
    distribution_config: DistributionConfig | None = None,
    orientation_config: OrientationConfig | None = None,
    style_config: BalancedStyleConfig | None = None,
    orientation_smoothing: float = 2.0,
) -> RenderedScene:
    """Render enabled objects independently and order them by z-index."""
    rendered = [
        render_scene_object(
            item,
            base_dir=base_dir,
            distribution_config=distribution_config,
            orientation_config=orientation_config,
            style_config=style_config,
            orientation_smoothing=orientation_smoothing,
        )
        for item in definition.objects
        if item.enabled
    ]
    if not rendered:
        raise ValueError("scene must contain at least one enabled object")
    rendered.sort(key=lambda item: (item.definition.z_index, item.definition.id))
    return RenderedScene(definition=definition, objects=tuple(rendered))


def _object_transform(item: RenderedSceneObject) -> str:
    transform = item.definition.transform
    return (
        f"translate({transform.x:.3f} {transform.y:.3f}) "
        f"rotate({transform.rotation:.3f}) "
        f"scale({transform.scale:.6f}) "
        f"translate({-item.mask_width / 2:.3f} {-item.mask_height / 2:.3f})"
    )


def render_scene_to_svg(scene: RenderedScene) -> str:
    """Compose local objects into one strict text-only SVG scene."""
    definition = scene.definition
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{definition.width}" '
        f'height="{definition.height}" viewBox="0 0 {definition.width} '
        f'{definition.height}" data-scene-id="{escape(definition.id, quote=True)}">',
        f'  <g id="scene_{escape(definition.id, quote=True)}" '
        f'data-scene-id="{escape(definition.id, quote=True)}">',
    ]
    for item in scene.objects:
        object_id = escape(item.definition.id, quote=True)
        word = escape(item.definition.word, quote=True)
        content.append(
            f'    <g id="object_{object_id}" data-object-id="{object_id}" '
            f'data-word="{word}" data-z-index="{item.definition.z_index}" '
            f'transform="{_object_transform(item)}">'
        )
        content.extend(
            render_glyph_groups(
                item.glyphs,
                id_prefix=item.definition.id,
                indent="      ",
            )
        )
        content.append("    </g>")
    content.append("  </g>")
    content.append("</svg>")
    return "\n".join(content)


def scene_manifest(scene: RenderedScene) -> dict[str, Any]:
    """Return local glyph states plus transforms, ready for animation later."""
    return {
        "scene": scene.definition.model_dump(),
        "object_order": [item.definition.id for item in scene.objects],
        "objects": [
            {
                "id": item.definition.id,
                "word": item.definition.word,
                "z_index": item.definition.z_index,
                "transform": item.definition.transform.model_dump(),
                "mask": {
                    "path": item.resolved_mask_path,
                    "width": item.mask_width,
                    "height": item.mask_height,
                },
                "glyphs": [glyph.model_dump() for glyph in item.glyphs],
            }
            for item in scene.objects
        ],
    }


def validate_rendered_scene(
    scene: RenderedScene,
    svg_content: str,
) -> dict[str, Any]:
    """Validate semantic isolation per object and strict typography globally."""
    object_reports: dict[str, dict[str, Any]] = {}
    for item in scene.objects:
        allowed = {
            character
            for character in item.definition.word.upper()
            if character.isalpha()
        }
        report = validate_scene(list(item.glyphs), allowed, svg_content)
        wrong_object_ids = sorted(
            {
                glyph.object_id
                for glyph in item.glyphs
                if glyph.object_id != item.definition.id
            }
        )
        report["object_id"] = item.definition.id
        report["word"] = item.definition.word
        report["wrong_object_ids"] = wrong_object_ids
        report["is_valid"] = report["is_valid"] and not wrong_object_ids
        object_reports[item.definition.id] = report

    forbidden = [tag for tag in FORBIDDEN_TAGS if tag in svg_content]
    all_ids = [item.definition.id for item in scene.objects]
    unique_ids = len(all_ids) == len(set(all_ids))
    valid = (
        not forbidden
        and unique_ids
        and all(report["is_valid"] for report in object_reports.values())
    )
    return {
        "is_valid": valid,
        "strict_mode_respected": not forbidden,
        "semantic_isolation_respected": all(
            report["semantic_characters_respected"]
            for report in object_reports.values()
        ),
        "unique_object_ids": unique_ids,
        "forbidden_tags_found": forbidden,
        "scene_id": scene.definition.id,
        "canvas": {
            "width": scene.definition.width,
            "height": scene.definition.height,
        },
        "object_order": all_ids,
        "object_count": len(scene.objects),
        "total_glyphs_rendered": len(scene.glyphs),
        "objects": object_reports,
    }
