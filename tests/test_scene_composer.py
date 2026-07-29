from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from engine.models import Glyph
from engine.scene_composer import (
    RenderedScene,
    RenderedSceneObject,
    render_scene,
    render_scene_object,
    render_scene_to_svg,
    validate_rendered_scene,
)
from engine.scene_models import SceneDefinition, SceneObject, SceneTransform


def _mask(path: Path, inset: int = 5) -> None:
    image = Image.new("L", (36, 36), color=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((inset, inset, 35 - inset, 35 - inset), fill=0)
    image.save(path)


def _object(
    identifier: str,
    word: str,
    mask_path: str,
    *,
    x: float,
    y: float,
    z_index: int,
    seed: int = 17,
) -> SceneObject:
    return SceneObject(
        id=identifier,
        word=word,
        mask_path=mask_path,
        transform=SceneTransform(x=x, y=y, scale=1.0),
        z_index=z_index,
        glyph_count=24,
        font_size_range=(5.0, 9.0),
        palette=["#172033", "#596773"],
        seed=seed,
    )


def test_scene_rejects_duplicate_object_ids() -> None:
    first = _object("same", "CAT", "cat.png", x=10, y=10, z_index=1)
    second = _object("same", "MOON", "moon.png", x=20, y=20, z_index=2)

    with pytest.raises(ValidationError):
        SceneDefinition(id="duplicate", objects=[first, second])


def test_scene_orders_objects_by_z_index_and_keeps_semantics(tmp_path: Path) -> None:
    _mask(tmp_path / "cat.png", inset=4)
    _mask(tmp_path / "moon.png", inset=8)
    scene = SceneDefinition(
        id="cat_moon",
        width=320,
        height=180,
        objects=[
            _object("cat_01", "CAT", "cat.png", x=140, y=110, z_index=3),
            _object("moon_01", "MOON", "moon.png", x=250, y=45, z_index=1),
        ],
    )

    rendered = render_scene(scene, base_dir=tmp_path)
    assert [item.definition.id for item in rendered.objects] == ["moon_01", "cat_01"]
    assert {glyph.character for glyph in rendered.objects[0].glyphs} <= set("MOON")
    assert {glyph.character for glyph in rendered.objects[1].glyphs} <= set("CAT")

    svg = render_scene_to_svg(rendered)
    assert svg.index('id="object_moon_01"') < svg.index('id="object_cat_01"')
    assert 'data-word="MOON"' in svg
    assert 'data-word="CAT"' in svg
    assert '<path' not in svg
    assert '<rect' not in svg

    report = validate_rendered_scene(rendered, svg)
    assert report["is_valid"] is True
    assert report["object_count"] == 2
    assert report["total_glyphs_rendered"] == 48


def test_transform_changes_do_not_regenerate_local_glyphs(tmp_path: Path) -> None:
    _mask(tmp_path / "cat.png")
    first = _object("cat_01", "CAT", "cat.png", x=50, y=60, z_index=1)
    moved = first.model_copy(
        update={"transform": SceneTransform(x=250, y=120, scale=0.6, rotation=15)}
    )

    original_render = render_scene_object(first, base_dir=tmp_path)
    moved_render = render_scene_object(moved, base_dir=tmp_path)

    original_glyphs = [glyph.model_dump() for glyph in original_render.glyphs]
    moved_glyphs = [glyph.model_dump() for glyph in moved_render.glyphs]
    assert original_glyphs == moved_glyphs


def test_validation_detects_character_from_another_object() -> None:
    cat_definition = _object("cat_01", "CAT", "unused.png", x=50, y=50, z_index=1)
    invalid_glyph = Glyph(
        id="cat_01_fill_0",
        object_id="cat_01",
        character="M",
        x=1,
        y=1,
        font_size=10,
        color="#172033",
    )
    rendered_object = RenderedSceneObject(
        definition=cat_definition,
        glyphs=(invalid_glyph,),
        mask_width=10,
        mask_height=10,
        resolved_mask_path="unused.png",
    )
    scene = RenderedScene(
        definition=SceneDefinition(id="invalid", objects=[cat_definition]),
        objects=(rendered_object,),
    )
    svg = render_scene_to_svg(scene)
    report = validate_rendered_scene(scene, svg)

    assert report["is_valid"] is False
    assert report["objects"]["cat_01"]["invalid_glyphs_found"] == ["M"]
