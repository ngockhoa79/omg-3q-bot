"""Cho biết bot nhận ra màn hình nào + điểm khớp từng màn hình.  py tools/where_am_i.py emulator-5556"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.device import Device
from core import screens

dev = Device(sys.argv[1])
img = dev.screen()
print("Màn hình:", screens.detect(dev, img))
for k, v in screens.scores(dev, img).items():
    print(f"  {k:14s} {v}")
print("Đã lưu ảnh:", screens.save_unknown(dev, img))
