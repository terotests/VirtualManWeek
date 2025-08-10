#!/usr/bin/env python3
"""Test script for the mode switch dialog"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from PySide6.QtWidgets import QApplication
from virtualmanweek.ui.mode_switch_dialog import ModeSwitchDialog

def test_dialog():
    app = QApplication(sys.argv)
    
    dialog = ModeSwitchDialog("Test Mode")
    result = dialog.exec()
    
    if result:
        description, manual_seconds = dialog.get_result()
        print(f"Dialog result: description='{description}', manual_seconds={manual_seconds}")
    else:
        print("Dialog was cancelled")
    
    app.quit()

if __name__ == "__main__":
    test_dialog()
