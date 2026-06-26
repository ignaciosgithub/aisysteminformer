"""Allow ``python -m aisysteminformer`` to invoke the CLI."""

from __future__ import annotations

import sys

from aisysteminformer.cli import main

if __name__ == "__main__":
    sys.exit(main())
