from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

_FRAME_NAME = re.compile(r"^frame_(\d+)\.png$")


@dataclass(frozen=True)
class VideoExportResult:
    output_path: Path
    frame_count: int
    fps: int
    command: tuple[str, ...]


def resolve_ffmpeg(explicit: str | Path | None = None) -> str:
    """Resolve an FFmpeg executable without making it a Python dependency."""
    if explicit is not None:
        candidate = str(explicit)
        explicit_path = Path(candidate)
        if explicit_path.is_file():
            return str(explicit_path.resolve())
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        raise ValueError(f"FFmpeg executable was not found: {candidate}")

    resolved = shutil.which("ffmpeg")
    if not resolved:
        raise ValueError(
            "FFmpeg was not found in PATH. Install FFmpeg or pass --ffmpeg with its executable path."
        )
    return resolved


def inspect_png_sequence(frames_dir: str | Path) -> tuple[list[Path], int]:
    directory = Path(frames_dir)
    if not directory.is_dir():
        raise ValueError(f"PNG frames directory was not found: {directory}")

    indexed: list[tuple[int, Path, int]] = []
    for path in directory.iterdir():
        match = _FRAME_NAME.fullmatch(path.name)
        if match:
            digits = match.group(1)
            indexed.append((int(digits), path, len(digits)))

    if not indexed:
        raise ValueError(f"no frame_*.png files were found in: {directory}")

    indexed.sort(key=lambda item: item[0])
    indexes = [item[0] for item in indexed]
    expected = list(range(len(indexes)))
    if indexes != expected:
        missing = sorted(set(expected) - set(indexes))
        raise ValueError(
            "PNG frame sequence must start at zero and be contiguous; "
            f"indexes={indexes[:10]}, missing={missing[:10]}"
        )

    paddings = {item[2] for item in indexed}
    if len(paddings) != 1:
        raise ValueError("PNG frame names must use one consistent zero-padding width")

    return [item[1] for item in indexed], paddings.pop()


def build_ffmpeg_command(
    *,
    ffmpeg: str,
    frames_dir: Path,
    padding: int,
    fps: int,
    output_path: Path,
    crf: int = 18,
    preset: str = "medium",
) -> list[str]:
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    if not 0 <= crf <= 51:
        raise ValueError("crf must be between 0 and 51")
    if not preset.strip():
        raise ValueError("preset cannot be blank")

    input_pattern = frames_dir / f"frame_%0{padding}d.png"
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(input_pattern),
        "-vf",
        "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def export_png_sequence_to_mp4(
    *,
    frames_dir: str | Path,
    output_path: str | Path,
    fps: int,
    ffmpeg: str | Path | None = None,
    crf: int = 18,
    preset: str = "medium",
    timeout_seconds: float | None = None,
) -> VideoExportResult:
    frames, padding = inspect_png_sequence(frames_dir)
    executable = resolve_ffmpeg(ffmpeg)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(
        ffmpeg=executable,
        frames_dir=Path(frames_dir).resolve(),
        padding=padding,
        fps=fps,
        output_path=output.resolve(),
        crf=crf,
        preset=preset,
    )

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "unknown FFmpeg error").strip()
        raise RuntimeError(f"FFmpeg failed with code {completed.returncode}: {details}")
    if not output.is_file():
        raise RuntimeError("FFmpeg reported success but the MP4 file was not created")

    return VideoExportResult(
        output_path=output.resolve(),
        frame_count=len(frames),
        fps=fps,
        command=tuple(command),
    )
