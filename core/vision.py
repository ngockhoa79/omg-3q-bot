"""Nhận diện ảnh mẫu (template matching)."""
from pathlib import Path
import cv2
import numpy as np

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_cache: dict = {}


def load_template(name: str) -> np.ndarray:
    if name not in _cache:
        path = TEMPLATE_DIR / f"{name}.png"
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Thiếu template: {path}")
        _cache[name] = img
    return _cache[name]


SCALES_WIDE = (0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.15)


def _scaled(tpl: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return tpl
    return cv2.resize(tpl, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def find(screen: np.ndarray, name: str, threshold: float = 0.85, region=None, scale: float = 1.0):
    """
    Tìm template trong ảnh. Trả về (cx, cy, score) nếu >= threshold, ngược lại None.
    region = (x1, y1, x2, y2) để giới hạn vùng tìm (nhanh và ít nhầm hơn).
    scale = hệ số phóng/thu template (dùng khi template cắt từ ảnh chụp bị lệch tỉ lệ).
    """
    tpl = _scaled(load_template(name), scale)
    ox = oy = 0
    if region:
        x1, y1, x2, y2 = region
        screen = screen[y1:y2, x1:x2]
        ox, oy = x1, y1
    th, tw = tpl.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return None
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, loc = cv2.minMaxLoc(res)
    if score < threshold:
        return None
    return (ox + loc[0] + tw // 2, oy + loc[1] + th // 2, float(score))


def red_dot(screen: np.ndarray, region, min_area=120, max_area=500):
    """Tìm chấm đỏ thông báo (hình tròn, đỏ đậm) trong vùng region=(x1,y1,x2,y2).
    Trả về (x, y) tâm chấm hoặc None. Lọc theo hình dạng để không nhầm với phần đỏ của icon."""
    x1, y1, x2, y2 = region
    roi = screen[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 150, 150), (8, 255, 255)) | cv2.inRange(hsv, (172, 150, 150), (180, 255, 255))
    n, _, st, cen = cv2.connectedComponentsWithStats(mask)
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if not (min_area <= a <= max_area):
            continue
        if not (0.7 <= w / h <= 1.4) or a / (w * h) < 0.6:
            continue
        return (x1 + int(cen[k][0]), y1 + int(cen[k][1]))
    return None


def find_scaled(screen: np.ndarray, name: str, threshold: float = 0.8, region=None, scales=SCALES_WIDE):
    """Thử nhiều tỉ lệ, trả về (cx, cy, score, scale) của tỉ lệ khớp nhất hoặc None."""
    best = None
    for sc in scales:
        hit = find(screen, name, 0.0, region, scale=sc)
        if hit and (best is None or hit[2] > best[2]):
            best = (hit[0], hit[1], hit[2], sc)
    if best and best[2] >= threshold:
        return best
    return None


def find_all(screen: np.ndarray, name: str, threshold: float = 0.8, region=None, scale: float = 1.0):
    """Tìm TẤT CẢ vị trí khớp (đã loại trùng lặp). Trả về list [(cx, cy, score)] xếp theo điểm giảm dần."""
    tpl = _scaled(load_template(name), scale)
    ox = oy = 0
    if region:
        x1, y1, x2, y2 = region
        screen = screen[y1:y2, x1:x2]
        ox, oy = x1, y1
    th, tw = tpl.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return []
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= threshold)
    cands = sorted(zip(res[ys, xs], xs, ys), reverse=True)
    out = []
    for score, x, y in cands:
        cx, cy = ox + x + tw // 2, oy + y + th // 2
        if all(abs(cx - ax) > tw // 2 or abs(cy - ay) > th // 2 for ax, ay, _ in out):
            out.append((cx, cy, float(score)))
    return out