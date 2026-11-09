"""Liệt kê các tab LDPlayer (index, tên, đang chạy?, cổng ADB):  py tools/list_instances.py"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.ldplayer import LDPlayer

cfg = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))
ld = LDPlayer(cfg["ld_console"], cfg["adb_path"])
for i in ld.list_instances():
    print(f"index={i['index']:<3} name={i['name']:<20} running={i['running']!s:<6} serial={ld.serial(i['index'])}")
