from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from engine.video_export import export_png_sequence_to_mp4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a contiguous PNG frame sequence to MP4 with FFmpeg"
    )
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument(
        "--ffmpeg",
        default=None,
        help="Optional FFmpeg executable path or command name",
    )
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--timeout", type=float, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.output.suffix.lower() != ".mp4":
        print("Erro: --output precisa terminar em .mp4")
        return 2

    try:
        result = export_png_sequence_to_mp4(
            frames_dir=args.frames_dir,
            output_path=args.output,
            fps=args.fps,
            ffmpeg=args.ffmpeg,
            crf=args.crf,
            preset=args.preset,
            timeout_seconds=args.timeout,
        )
    except (OSError, ValueError, RuntimeError) as error:
        print("Erro ao exportar o vídeo:")
        print(error)
        return 2

    report_path = result.output_path.with_name(
        result.output_path.stem + "_export.json"
    )
    report_path.write_text(
        json.dumps(
            {
                "is_valid": True,
                "output_path": str(result.output_path),
                "frame_count": result.frame_count,
                "fps": result.fps,
                "command": list(result.command),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        f"MP4 exportado: {result.frame_count} frames a {result.fps} fps -> "
        f"{result.output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
