from __future__ import annotations

import sys

from render_object_from_mask import main


if __name__ == "__main__":
    arguments = list(sys.argv[1:])
    if "--layer-mode" not in arguments:
        arguments = ["--layer-mode", "balanced", *arguments]
    raise SystemExit(main(arguments))
