"""Tìm tên package của game đang cài:  py tools/find_package.py emulator-5556"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.adb import Adb

cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
adb = Adb(cfg["adb_path"], sys.argv[1])
pk = [l.replace("package:", "").strip() for l in adb.shell("pm", "list", "packages", "-3").splitlines()]
print("Các app bên thứ ba đã cài:")
for p in pk:
    mark = "   <-- có thể là game" if any(k in p.lower() for k in ("omg", "3q", "vng", "tamquoc")) else ""
    print(" ", p, mark)
print("\nMở game rồi chạy lại lệnh dưới để biết app đang ở trước mặt:")
print("  adb -s", sys.argv[1], "shell dumpsys window | findstr mCurrentFocus")
