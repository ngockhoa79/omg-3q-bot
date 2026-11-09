"""Lớp bọc ADB: chụp màn hình, tap, swipe, back, gõ chữ, bật/tắt app."""
import subprocess
import numpy as np
import cv2

# Ký tự cần thêm dấu \ khi gửi qua 'adb shell input text'
_SHELL_SPECIAL = set("\\'\"&|;<>()$`*?!#~{}[]^")


REF_RESOLUTION = (1280, 720)   # độ phân giải chuẩn của ảnh mẫu


class Adb:
    """Mọi toạ độ bên ngoài đều tính theo 1280x720. Nếu máy có độ phân giải khác (cùng tỉ lệ 16:9, vd 1600x900)
    thì ảnh chụp được thu về 1280x720 và toạ độ chạm được quy đổi ngược lại."""

    def __init__(self, adb_path: str, serial: str, ref=REF_RESOLUTION):
        self.adb = adb_path
        self.serial = serial
        self.ref = ref
        self._real = None          # kích thước thật của máy (w, h)

    def _run(self, *args, timeout=15) -> bytes:
        cmd = [self.adb, "-s", self.serial, *args]
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"adb lỗi {cmd}: {r.stderr.decode(errors='ignore')}")
        return r.stdout

    def shell(self, *args, timeout=15) -> str:
        return self._run("shell", *args, timeout=timeout).decode(errors="ignore").strip()

    def screenshot(self) -> np.ndarray:
        """Trả về ảnh BGR (OpenCV). Dùng exec-out để lấy PNG trực tiếp."""
        data = self._run("exec-out", "screencap", "-p")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("Không decode được ảnh screencap")
        h, w = img.shape[:2]
        self._real = (w, h)
        if (w, h) != tuple(self.ref):
            img = cv2.resize(img, tuple(self.ref), interpolation=cv2.INTER_AREA)
        return img

    def _scale(self):
        if self._real is None:
            self._real = self.size()
        return self._real[0] / self.ref[0], self._real[1] / self.ref[1]

    def tap(self, x: int, y: int):
        sx, sy = self._scale()
        self._run("shell", "input", "tap", str(round(x * sx)), str(round(y * sy)))

    def swipe(self, x1, y1, x2, y2, ms=300):
        sx, sy = self._scale()
        vals = (round(x1 * sx), round(y1 * sy), round(x2 * sx), round(y2 * sy), int(ms))
        self._run("shell", "input", "swipe", *[str(v) for v in vals])

    def back(self):
        self._run("shell", "input", "keyevent", "4")

    def keyevent(self, code: int):
        self._run("shell", "input", "keyevent", str(int(code)))

    def size(self):
        out = self._run("shell", "wm", "size").decode()
        w, h = out.strip().split(":")[-1].strip().split("x")
        return int(w), int(h)

    # ---- nhập liệu ----
    @staticmethod
    def escape_input_text(text: str) -> str:
        """Chuẩn bị chuỗi cho 'input text'. Chỉ hỗ trợ ASCII; khoảng trắng -> %s."""
        out = []
        for ch in text:
            if ord(ch) > 126 or ord(ch) < 32:
                raise ValueError("input text chỉ hỗ trợ ký tự ASCII hiển thị được")
            if ch == "%":
                raise ValueError("Ký tự % không gõ được qua adb input text")
            if ch == " ":
                out.append("%s")
            elif ch in _SHELL_SPECIAL:
                out.append("\\" + ch)
            else:
                out.append(ch)
        return "".join(out)

    def type_text(self, text: str):
        self._run("shell", "input", "text", self.escape_input_text(text))

    def clear_field(self, max_chars: int = 40):
        """Xoá nội dung ô đang focus: nhảy tới cuối rồi xoá lùi."""
        self.keyevent(123)                     # KEYCODE_MOVE_END
        for _ in range(max_chars):
            self.keyevent(67)                  # KEYCODE_DEL

    # ---- ứng dụng ----
    def force_stop(self, package: str):
        self.shell("am", "force-stop", package)

    def start_app(self, package: str):
        self.shell("monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")

    def boot_completed(self) -> bool:
        try:
            return self.shell("getprop", "sys.boot_completed") == "1"
        except Exception:
            return False