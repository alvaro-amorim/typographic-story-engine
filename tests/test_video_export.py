from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import engine.video_export as video_export
import export_video
from engine.video_export import VideoExportResult


def _frames(directory: Path, count: int, padding: int = 4) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (directory / f"frame_{index:0{padding}d}.png").write_bytes(b"png")


def test_inspect_png_sequence_detects_padding_and_order(tmp_path: Path) -> None:
    frames = tmp_path / "frames"
    _frames(frames, 3, padding=5)

    paths, padding = video_export.inspect_png_sequence(frames)

    assert [path.name for path in paths] == [
        "frame_00000.png",
        "frame_00001.png",
        "frame_00002.png",
    ]
    assert padding == 5


def test_inspect_png_sequence_rejects_gaps(tmp_path: Path) -> None:
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "frame_0000.png").write_bytes(b"png")
    (frames / "frame_0002.png").write_bytes(b"png")

    with pytest.raises(ValueError, match="contiguous"):
        video_export.inspect_png_sequence(frames)


def test_build_command_uses_h264_even_dimensions_and_faststart(tmp_path: Path) -> None:
    output = tmp_path / "movie.mp4"
    command = video_export.build_ffmpeg_command(
        ffmpeg="ffmpeg",
        frames_dir=tmp_path,
        padding=4,
        fps=12,
        output_path=output,
        crf=20,
        preset="fast",
    )

    assert command[0] == "ffmpeg"
    assert "frame_%04d.png" in command
    assert "libx264" in command
    assert "pad=ceil(iw/2)*2:ceil(ih/2)*2" in command
    assert "yuv420p" in command
    assert "+faststart" in command
    assert command[-1] == str(output)


def test_export_invokes_ffmpeg_and_returns_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = tmp_path / "frames"
    _frames(frames, 4)
    output = tmp_path / "movie.mp4"
    captured: dict[str, object] = {}

    monkeypatch.setattr(video_export, "resolve_ffmpeg", lambda explicit=None: "ffmpeg")

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"fake-mp4")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(video_export.subprocess, "run", fake_run)

    result = video_export.export_png_sequence_to_mp4(
        frames_dir=frames,
        output_path=output,
        fps=8,
    )

    assert result.output_path == output.resolve()
    assert result.frame_count == 4
    assert result.fps == 8
    assert output.read_bytes() == b"fake-mp4"
    assert captured["kwargs"]["check"] is False


def test_export_surfaces_ffmpeg_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = tmp_path / "frames"
    _frames(frames, 2)
    monkeypatch.setattr(video_export, "resolve_ffmpeg", lambda explicit=None: "ffmpeg")
    monkeypatch.setattr(
        video_export.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="codec error",
        ),
    )

    with pytest.raises(RuntimeError, match="codec error"):
        video_export.export_png_sequence_to_mp4(
            frames_dir=frames,
            output_path=tmp_path / "movie.mp4",
            fps=8,
        )


def test_cli_writes_export_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = tmp_path / "frames"
    _frames(frames, 3)
    output = tmp_path / "movie.mp4"

    def fake_export(**kwargs):
        output.write_bytes(b"mp4")
        return VideoExportResult(
            output_path=output.resolve(),
            frame_count=3,
            fps=6,
            command=("ffmpeg", "fake"),
        )

    monkeypatch.setattr(export_video, "export_png_sequence_to_mp4", fake_export)
    result = export_video.main(
        [
            "--frames-dir",
            str(frames),
            "--output",
            str(output),
            "--fps",
            "6",
        ]
    )
    report = json.loads(
        (tmp_path / "movie_export.json").read_text(encoding="utf-8")
    )

    assert result == 0
    assert report["is_valid"] is True
    assert report["frame_count"] == 3
    assert report["fps"] == 6
