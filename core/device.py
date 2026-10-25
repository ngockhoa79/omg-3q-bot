"""Device = 1 instance LDPlayer. Các hàm cấp cao cho task dùng."""
import json
import logging
import random
import time
from pathlib import Path

from core.adb import Adb
from core import vision

CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text(encoding="utf-8"))


class Device:
    def __init__(self, serial: str):
        self.serial = serial
        self.adb = Adb(CFG["adb_path"], serial)
        self.log = logging.getLogger(serial)
        self.threshold = CFG["match_threshold"]

    def sleep_rand(self):
        lo, hi = CFG["delay_range"]
        time.sleep(random.uniform(lo, hi))

    def screen(self):
        return self.adb.screenshot()

    def tap(self, x, y):
        j = CFG["jitter_px"]
        self.adb.tap(x + random.randint(-j, j), y + random.randint(-j, j))
        self.sleep_rand()

    def find(self, name, region=None, screen=None, threshold=None):
        return vision.find(screen if screen is not None else self.screen(),
                           name, threshold or self.threshold, region)

    def red_dot(self, region):
        """Có chấm đỏ thông báo trong vùng không -> (x,y) hoặc None."""
        return vision.red_dot(self.screen(), region)

    def exists(self, name, region=None, threshold=None) -> bool:
        return self.find(name, region, threshold=threshold) is not None

    def click(self, name, region=None, threshold=None) -> bool:
        """Tìm template và tap vào giữa. True nếu bấm được."""
        hit = self.find(name, region, threshold=threshold)
        if not hit:
            return False
        x, y, score = hit
        self.log.info("click %s (%d,%d) score=%.2f", name, x, y, score)
        self.tap(x, y)
        return True

    def wait_for(self, name, timeout=30, region=None, threshold=None):
        """Chờ template xuất hiện, trả về (x,y,score) hoặc None khi hết giờ."""
        end = time.time() + timeout
        while time.time() < end:
            hit = self.find(name, region, threshold=threshold)
            if hit:
                return hit
            time.sleep(CFG["poll_interval"])
        return None

    def wait_and_click(self, name, timeout=30, region=None, threshold=None) -> bool:
        hit = self.wait_for(name, timeout, region, threshold)
        if not hit:
            self.log.warning("hết giờ chờ %s", name)
            return False
        self.log.info("click %s (%d,%d) score=%.2f", name, *hit)
        self.tap(hit[0], hit[1])
        return True