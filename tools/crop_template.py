"""
Cắt template từ ảnh chụp bằng ADB.
  python tools/crop_template.py <serial>                              -> lưu templates/_screen.png để xem tọa độ
  python tools/crop_template.py <serial> <ten_template> x1 y1 x2 y2   -> cắt và lưu templates/<ten>.png
"""
import sys
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.device import Device

serial, *rest = sys.argv[1:]
dev = Device(serial)
img = dev.screen()
out = Path(__file__).resolve().parent.parent / "templates"
if not rest:
    cv2.imwrite(str(out / "_screen.png"), img)
    print("Đã lưu templates/_screen.png", img.shape[1], "x", img.shape[0])
else:
    name, x1, y1, x2, y2 = rest[0], *map(int, rest[1:5])
    cv2.imwrite(str(out / f"{name}.png"), img[y1:y2, x1:x2])
    print("Đã lưu", name)
