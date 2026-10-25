"""Lớp bọc ADB: chụp màn hình, tap, swipe, back."""
import subprocess
import numpy as np
import cv2


class Adb:
    def __init__(self, adb_path: str, serial: str):
        self.adb = adb_path
        self.serial = serial

    def _run(self, *args, timeout=15) -> bytes:
        cmd = [self.adb, "-s", self.serial, *args]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"adb lỗi {cmd}: {r.stderr.decode(errors='ignore')}")
        return r.stdout

    def screenshot(self) -> np.ndarray:
        """Trả về ảnh BGR (OpenCV). Dùng exec-out để lấy PNG trực tiếp."""
        data = self._run("exec-out", "screencap", "-p")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("Không decode được ảnh screencap")
        return img

    def tap(self, x: int, y: int):
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1, y1, x2, y2, ms=300):
        self._run("shell", "input", "swipe", *[str(int(v)) for v in (x1, y1, x2, y2, ms)])

    def back(self):
        self._run("shell", "input", "keyevent", "4")

    def size(self):
        out = self._run("shell", "wm", "size").decode()
        w, h = out.strip().split(":")[-1].strip().split("x")
        return int(w), int(h)
