"""Lemonade Wars — desktop entry point.

Run with:  python main.py
Web build: pygbag builds this same entry under web/ (see build_web.sh).
"""

import os
import sys

# Make the src/ layout importable without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from lemonwars.ui.app import main  # noqa: E402

if __name__ == "__main__":
    main()
