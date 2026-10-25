"""Nhận diện bot đang ở màn hình nào.

Thứ tự trong SCREENS rất quan trọng: màn hình nào có thể 'chồng' lên màn hình khác
(popup/banner chồng lên màn hình bên dưới) thì phải đứng TRƯỚC.
"""
import time
from pathlib import Path

import cv2

from core import vision

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
TEMPLATE_DIR = vision.TEMPLATE_DIR

# (tên màn hình, template, vùng tìm, ngưỡng, danh sách tỉ lệ thử)
#  ngưỡng None = ngưỡng mặc định; tỉ lệ None = chỉ thử 1.0
SCREENS = [
    ("login",           "btn_vao_game",          (450, 540, 830, 700),  None, None),
    ("popup_tap_close", "txt_nhan_vung_trong",   (300, 640, 980, 720),  None, None),
    ("banner",          "btn_den",               (600, 560, 1000, 713), None, None),
    ("hero_select",     "scr_chon_tuong",        None,                  0.7,  None),
    ("thay_tuong",      "scr_thay_tuong",        (300, 0, 980, 100),    0.8,  vision.SCALES_WIDE),  # popup chọn tướng ra trận
    ("doi_hinh",        "scr_doi_hinh",          (100, 0, 300, 56),     None, None),
    ("hanh_thuong",     "scr_hanh_thuong",       (100, 10, 260, 66),    None, None),
    ("time_machine",    "scr_co_may_thoi_gian",  (0, 170, 130, 290),    None, None),   # màn chính sự kiện
    ("home",            "marker_man_hinh_chinh", (600, 0, 780, 70),     None, None),
]


def _available():
    return [s for s in SCREENS if (TEMPLATE_DIR / f"{s[1]}.png").exists()]


def _match(dev, img, tpl, region, thr, scales):
    if scales:
        return vision.find_scaled(img, tpl, thr or dev.threshold, region, scales)
    return vision.find(img, tpl, thr or dev.threshold, region)


def scores(dev, screen=None):
    """Trả về {tên màn hình: điểm khớp} để debug."""
    img = screen if screen is not None else dev.screen()
    out = {}
    for name, tpl, region, thr, scales in _available():
        if scales:
            hit = vision.find_scaled(img, tpl, 0.0, region, scales)
        else:
            hit = vision.find(img, tpl, 0.0, region)
        out[name] = round(hit[2], 3) if hit else 0.0
    return out


def detect(dev, screen=None) -> str:
    """Tên màn hình hiện tại, hoặc 'unknown'."""
    img = screen if screen is not None else dev.screen()
    for name, tpl, region, thr, scales in _available():
        if _match(dev, img, tpl, region, thr, scales):
            return name
    return "unknown"


def save_unknown(dev, screen=None) -> Path:
    """Lưu ảnh màn hình lạ vào logs/ để bạn gửi lại cho mình làm template."""
    img = screen if screen is not None else dev.screen()
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"unknown_{dev.serial}_{time.strftime('%H%M%S')}.png"
    cv2.imwrite(str(path), img)
    return path