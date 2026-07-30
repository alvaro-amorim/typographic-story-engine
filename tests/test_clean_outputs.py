from __future__ import annotations

from pathlib import Path

import pytest

import commands.clean_outputs as cleanup


def test_clean_outputs_removes_generated_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repo"
    outputs = repository / "outputs"
    outputs.mkdir(parents=True)
    (outputs / ".gitkeep").write_text("", encoding="utf-8")
    (outputs / "preview.png").write_bytes(b"png")
    nested = outputs / "job" / "frames"
    nested.mkdir(parents=True)
    (nested / "frame.svg").write_text("<svg/>", encoding="utf-8")

    monkeypatch.setattr(cleanup, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(cleanup, "DEFAULT_OUTPUTS", outputs)

    removed = cleanup.clean_outputs(outputs)

    assert {path.name for path in removed} == {"preview.png", "job"}
    assert [path.name for path in outputs.iterdir()] == [".gitkeep"]


def test_clean_outputs_refuses_outside_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    outputs = repository / "outputs"
    monkeypatch.setattr(cleanup, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(cleanup, "DEFAULT_OUTPUTS", outputs)

    with pytest.raises(ValueError, match="outside the repository"):
        cleanup.clean_outputs(tmp_path / "elsewhere")
