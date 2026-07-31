from __future__ import annotations

import sys
from collections.abc import Sequence

from run_api import main as run_api_main


def main(argv: Sequence[str] | None = None) -> int:
    forwarded = list(sys.argv[1:] if argv is None else argv)
    if "--open-browser" not in forwarded:
        forwarded.insert(0, "--open-browser")
    return run_api_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
