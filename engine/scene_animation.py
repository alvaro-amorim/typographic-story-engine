from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

from engine.animation_models import (
    AnimationFrameState,
    AnimationManifest,
    SceneAnimationSpec,
)
from engine.scene_composer import (
    LoadedSceneObject,
    load_scene_objects,
    load_scene_spec,
    render_scene_svg,
    resolve_scene_paths,
    validate_composed_scene,
)
from engine.scene_models import SceneObjectSpec, SceneSpec, SceneTransform


@dataclass(frozen=True)
class PreparedSceneAnimation:
    spec: SceneAnimationSpec
    from_scene_path: Path
    to_scene_path: Path
    from_scene: SceneSpec
    to_scene: SceneSpec
    source_objects: tuple[LoadedSceneObject, ...]

    @property
    def object_ids(self) -> tuple[str, ...]:
        return tuple(item.spec.id for item in self.source_objects)


@dataclass(frozen=True)
class RenderedAnimationFrame:
    state: AnimationFrameState
    scene: SceneSpec
    objects: tuple[LoadedSceneObject, ...]
    svg: str
    validation: dict[str, object]


def load_animation_spec(path: str | Path) -> SceneAnimationSpec:
    animation_path = Path(path)
    try:
        payload = json.loads(animation_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid animation JSON: {error}") from error
    return SceneAnimationSpec.model_validate(payload)


def resolve_animation_paths(
    spec: SceneAnimationSpec,
    animation_path: str | Path,
) -> SceneAnimationSpec:
    base_directory = Path(animation_path).resolve().parent

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else (base_directory / path).resolve()

    return spec.model_copy(
        update={
            "from_scene": resolve(spec.from_scene),
            "to_scene": resolve(spec.to_scene),
        }
    )


def easing_value(name: str, progress: float) -> float:
    value = max(0.0, min(1.0, float(progress)))
    if name == "linear":
        return value
    if name == "ease_in":
        return value * value
    if name == "ease_out":
        return 1.0 - (1.0 - value) * (1.0 - value)
    if name == "ease_in_out":
        return 0.5 - 0.5 * math.cos(math.pi * value)
    raise ValueError(f"unsupported easing: {name}")


def _resolved_scene(path: Path) -> SceneSpec:
    if not path.is_file():
        raise ValueError(f"scene file not found: {path}")
    return resolve_scene_paths(load_scene_spec(path), path)


def _validate_scene_pair(from_scene: SceneSpec, to_scene: SceneSpec) -> None:
    if (from_scene.width, from_scene.height) != (to_scene.width, to_scene.height):
        raise ValueError("animation scenes must use the same canvas dimensions")
    if from_scene.background != to_scene.background:
        raise ValueError("background changes are not supported in object-animation v0")

    from_objects = {item.id: item for item in from_scene.objects}
    to_objects = {item.id: item for item in to_scene.objects}
    if set(from_objects) != set(to_objects):
        missing_from_end = sorted(set(from_objects) - set(to_objects))
        missing_from_start = sorted(set(to_objects) - set(from_objects))
        raise ValueError(
            "animation scenes must contain the same object IDs; "
            f"only_from={missing_from_end}, only_to={missing_from_start}"
        )

    for identifier in sorted(from_objects):
        start = from_objects[identifier]
        end = to_objects[identifier]
        if start.word != end.word:
            raise ValueError(f"object '{identifier}' changes semantic word")
        if start.glyphs_path.resolve() != end.glyphs_path.resolve():
            raise ValueError(f"object '{identifier}' changes glyph source")
        if start.z_index != end.z_index:
            raise ValueError(f"object '{identifier}' changes z_index")


def prepare_scene_animation(spec: SceneAnimationSpec) -> PreparedSceneAnimation:
    from_path = spec.from_scene.resolve()
    to_path = spec.to_scene.resolve()
    from_scene = _resolved_scene(from_path)
    to_scene = _resolved_scene(to_path)
    _validate_scene_pair(from_scene, to_scene)
    source_objects = tuple(load_scene_objects(from_scene))
    return PreparedSceneAnimation(
        spec=spec,
        from_scene_path=from_path,
        to_scene_path=to_path,
        from_scene=from_scene,
        to_scene=to_scene,
        source_objects=source_objects,
    )


def _lerp(start: float, end: float, progress: float) -> float:
    return start + (end - start) * progress


def _lerp_rotation(start: float, end: float, progress: float) -> float:
    delta = ((end - start + 180.0) % 360.0) - 180.0
    return start + delta * progress


def interpolate_transform(
    start: SceneTransform,
    end: SceneTransform,
    progress: float,
    *,
    start_visible: bool,
    end_visible: bool,
) -> SceneTransform:
    start_opacity = start.opacity if start_visible else 0.0
    end_opacity = end.opacity if end_visible else 0.0
    mirror_x = start.mirror_x if progress < 0.5 else end.mirror_x
    return SceneTransform(
        x=_lerp(start.x, end.x, progress),
        y=_lerp(start.y, end.y, progress),
        scale_x=_lerp(start.scale_x, end.scale_x, progress),
        scale_y=_lerp(start.scale_y, end.scale_y, progress),
        rotation=_lerp_rotation(start.rotation, end.rotation, progress),
        opacity=_lerp(start_opacity, end_opacity, progress),
        mirror_x=mirror_x,
    )


def interpolate_scene(
    prepared: PreparedSceneAnimation,
    progress: float,
) -> tuple[SceneSpec, float]:
    raw = max(0.0, min(1.0, float(progress)))
    eased = easing_value(prepared.spec.easing, raw)
    end_by_id = {item.id: item for item in prepared.to_scene.objects}
    objects: list[SceneObjectSpec] = []

    for start in prepared.from_scene.objects:
        end = end_by_id[start.id]
        transform = interpolate_transform(
            start.transform,
            end.transform,
            eased,
            start_visible=start.visible,
            end_visible=end.visible,
        )
        objects.append(
            start.model_copy(
                update={
                    "transform": transform,
                    "visible": start.visible or end.visible,
                }
            )
        )

    scene = prepared.from_scene.model_copy(
        update={
            "id": prepared.spec.id,
            "objects": objects,
        }
    )
    return scene, eased


def _objects_for_scene(
    prepared: PreparedSceneAnimation,
    scene: SceneSpec,
) -> tuple[LoadedSceneObject, ...]:
    spec_by_id = {item.id: item for item in scene.objects}
    objects = [
        LoadedSceneObject(
            spec=spec_by_id[item.spec.id],
            glyphs=item.glyphs,
            resolved_path=item.resolved_path,
        )
        for item in prepared.source_objects
    ]
    objects.sort(key=lambda item: (item.spec.z_index, item.spec.id))
    return tuple(objects)


def frame_count(spec: SceneAnimationSpec) -> int:
    return max(2, int(round(spec.duration_seconds * spec.fps)) + 1)


def iter_animation_frames(
    prepared: PreparedSceneAnimation,
) -> Iterator[RenderedAnimationFrame]:
    total = frame_count(prepared.spec)
    for index in range(total):
        progress = index / (total - 1)
        scene, eased = interpolate_scene(prepared, progress)
        objects = _objects_for_scene(prepared, scene)
        svg = render_scene_svg(scene, objects)
        validation = validate_composed_scene(scene, objects, svg)
        transforms = {
            item.id: {
                **item.transform.model_dump(),
                "visible": item.visible,
            }
            for item in scene.objects
        }
        state = AnimationFrameState(
            index=index,
            timestamp_seconds=min(
                prepared.spec.duration_seconds,
                index / prepared.spec.fps,
            ),
            progress=progress,
            eased_progress=eased,
            object_transforms=transforms,
        )
        yield RenderedAnimationFrame(
            state=state,
            scene=scene,
            objects=objects,
            svg=svg,
            validation=validation,
        )


def build_animation_manifest(
    prepared: PreparedSceneAnimation,
    frames: Sequence[RenderedAnimationFrame],
) -> AnimationManifest:
    return AnimationManifest(
        id=prepared.spec.id,
        duration_seconds=prepared.spec.duration_seconds,
        fps=prepared.spec.fps,
        easing=prepared.spec.easing,
        frame_count=len(frames),
        from_scene=str(prepared.from_scene_path),
        to_scene=str(prepared.to_scene_path),
        object_ids=list(prepared.object_ids),
        frames=[frame.state for frame in frames],
    )


def validate_animation_frames(
    prepared: PreparedSceneAnimation,
    frames: Sequence[RenderedAnimationFrame],
) -> dict[str, object]:
    invalid_frames = [
        frame.state.index for frame in frames if not frame.validation["is_valid"]
    ]
    expected_count = frame_count(prepared.spec)
    endpoints_present = bool(frames) and math.isclose(
        frames[0].state.progress, 0.0
    ) and math.isclose(frames[-1].state.progress, 1.0)
    return {
        "is_valid": not invalid_frames
        and len(frames) == expected_count
        and endpoints_present,
        "animation_id": prepared.spec.id,
        "expected_frame_count": expected_count,
        "generated_frame_count": len(frames),
        "endpoints_present": endpoints_present,
        "invalid_frames": invalid_frames,
        "object_ids": list(prepared.object_ids),
        "glyphs_reused_per_frame": sum(
            len(item.glyphs) for item in prepared.source_objects
        ),
    }
