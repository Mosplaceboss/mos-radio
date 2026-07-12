"""Mo's Place Inventory entry point."""

from __future__ import annotations

import sys
from pathlib import Path

INVENTORY_ROOT = Path(__file__).resolve().parent.parent
if str(INVENTORY_ROOT) not in sys.path:
    sys.path.insert(0, str(INVENTORY_ROOT))

from app.ui.main_window import InventoryApplication


def main() -> None:
    InventoryApplication().run()


if __name__ == "__main__":
    main()
