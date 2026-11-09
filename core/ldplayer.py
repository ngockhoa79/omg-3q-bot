"""Điều khiển LDPlayer 9 qua ldconsole.exe (mở/tắt tab, chờ khởi động xong)."""
import logging
import subprocess
import time

from core.adb import Adb

log = logging.getLogger("ldplayer")


class LDPlayer:
    def __init__(self, console_path: str, adb_path: str):
        self.console = console_path
        self.adb_path = adb_path

    def _run(self, *args, timeout=60) -> str:
        r = subprocess.run([self.console, *map(str, args)], capture_output=True, timeout=timeout)
        return r.stdout.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def serial(index: int) -> str:
        """Tab index N dùng cổng ADB 5554 + 2N (tab 1 -> emulator-5556)."""
        return f"emulator-{5554 + 2 * int(index)}"

    def adb(self, index: int) -> Adb:
        return Adb(self.adb_path, self.serial(index))

    def list_instances(self):
        """[{'index':1,'name':'LDPlayer-1','running':True}, ...] (từ lệnh list2)."""
        out = []
        for line in self._run("list2").splitlines():
            p = line.strip().split(",")
            if len(p) >= 5 and p[0].isdigit():
                out.append({"index": int(p[0]), "name": p[1], "running": p[4] == "1"})
        return out

    def is_running(self, index: int) -> bool:
        return self._run("isrunning", "--index", index).lower() == "running"

    def launch(self, index: int):
        log.info("Mở tab LDPlayer %s", index)
        self._run("launch", "--index", index)

    def quit(self, index: int):
        log.info("Tắt tab LDPlayer %s", index)
        self._run("quit", "--index", index)

    def configure(self, index: int, resolution="1280,720,240", cpu=2, memory=2048):
        """Đặt độ phân giải/CPU/RAM. Chỉ áp dụng được khi tab đang tắt."""
        self._run("modify", "--index", index, "--resolution", resolution, "--cpu", cpu, "--memory", memory)

    def wait_boot(self, index: int, timeout: int = 180) -> bool:
        adb = self.adb(index)
        end = time.time() + timeout
        while time.time() < end:
            if adb.boot_completed():
                return True
            time.sleep(3)
        return False

    def ensure_running(self, index: int, timeout: int = 180, configure: dict = None) -> bool:
        """Đảm bảo tab đã chạy và Android khởi động xong. True nếu sẵn sàng."""
        if not self.is_running(index):
            if configure:
                self.configure(index, **configure)
            self.launch(index)
        return self.wait_boot(index, timeout)
