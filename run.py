"""Launch the MHKiT-DOLFyN GUI application."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from mhkit_dolfyn_gui.app import main

if __name__ == "__main__":
    main()
