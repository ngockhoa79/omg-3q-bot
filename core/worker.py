"""1 worker = 1 tab LDPlayer: lần lượt lấy acc từ hàng đợi, đăng nhập, chạy kịch bản, ghi kết quả vào Excel."""
import logging
import queue
import random
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import cv2

SHOT_DIR = Path(__file__).resolve().parent / "logs" / "screens"


class Services:
    """Gom các hàm bên ngoài vào một chỗ để dễ thay thế khi test.
    restart_game(dev) -> bool ; login(dev, username, password, server) -> (ok, err) ; run(dev, report, timeout) -> (ok, ctx)"""
    def __init__(self, ld, store, make_device, restart_game, login, run):
        self.ld, self.store, self.make_device = ld, store, make_device
        self.restart_game, self.login, self.run = restart_game, login, run


class AccountWorker(threading.Thread):
    def __init__(self, tab: int, q: "queue.Queue", svc: Services, cfg: dict, stop: threading.Event, start_delay: float = 0):
        super().__init__(name=f"tab{tab}", daemon=True)
        self.tab, self.q, self.svc, self.cfg, self.stop_evt = tab, q, svc, cfg, stop
        self.start_delay = start_delay
        self.store = svc.store
        self.serial = svc.ld.serial(tab)
        self.logger = logging.getLogger(f"tab{tab}")
        self.current = ""
        self._last_screen = None
        self.done = self.failed = 0

    # ---- ghi trạng thái ----
    def _log(self, level, msg):
        getattr(self.logger, level.lower() if level != "WARN" else "warning")(msg)
        self.store.add_log(self.tab, self.current, level, msg)

    def _inst(self, **f):
        self.store.update_instance(self.tab, Serial=self.serial, Updated=datetime.now(), **f)

    def _report(self, screen, ctx):
        """Gọi mỗi vòng của runner; chỉ ghi khi màn hình đổi để đỡ ghi Excel liên tục."""
        if screen == self._last_screen:
            return
        self._last_screen = screen
        self._inst(Screen=screen, Step=f"đang ở: {screen}")
        self.store.update_account(self.current, Step=screen)

    # ---- vòng đời ----
    def run(self):
        try:
            if self.start_delay:
                self._inst(Account="", State="Idle", Step=f"chờ {self.start_delay:.0f}s để so le thời gian")
                if self.stop_evt.wait(self.start_delay):
                    return
            self._inst(State="Starting", Step="mở tab LDPlayer", Since=datetime.now())
            ld_cfg = None
            if self.cfg.get("apply_instance_settings"):
                ld_cfg = {"resolution": "1280,720,240", "cpu": self.cfg.get("instance_cpu", 2),
                          "memory": self.cfg.get("instance_memory", 2048)}
            if not self.svc.ld.ensure_running(self.tab, self.cfg.get("boot_timeout_sec", 180), ld_cfg):
                self._log("ERROR", "Tab LDPlayer không khởi động được")
                self._inst(State="Error", Step="tab không khởi động được")
                return
            dev = self.svc.make_device(self.serial)

            while not self.stop_evt.is_set():
                try:
                    acc = self.q.get_nowait()
                except queue.Empty:
                    break
                self._process(dev, acc)
                lo, hi = self.cfg.get("between_accounts_sec", [3, 8])
                self.stop_evt.wait(random.uniform(lo, hi))
        except Exception as e:               # lỗi bất ngờ của cả worker
            self._log("ERROR", f"Worker lỗi: {type(e).__name__}: {e}")
            self.logger.debug(traceback.format_exc())
            self._inst(State="Error", Step=f"lỗi worker: {e}")
        finally:
            if self.cfg.get("quit_when_done"):
                try:
                    self.svc.ld.quit(self.tab)
                except Exception:
                    pass
            self._inst(State="Stopped", Account="", Screen="", Step=f"xong ({self.done} OK, {self.failed} lỗi)")

    def _process(self, dev, acc):
        u = self.current = acc.username
        self._last_screen = None
        t0, started = time.time(), datetime.now()
        self.store.update_account(u, Status="Running", Step="khởi động game", Instance=self.tab, LastRun=started,
                                  Error="", Screenshot="", DurationSec="")
        self._inst(Account=u, State="LoggingIn", Screen="", Step="khởi động game", Since=started)
        self._log("INFO", f"Bắt đầu acc {u}")

        status, err, ctx = "Error", "", {}
        stage = "khởi động game"
        try:
            if not self.svc.restart_game(dev):
                err = "Không mở được game / không thấy màn hình đăng nhập"
            else:
                stage = "đăng nhập"
                self.store.update_account(u, Step=stage)
                self._inst(Step=stage)
                ok, e = self.svc.login(dev, u, acc.password, acc.server)
                if not ok:
                    status, err = "LoginFailed", e
                else:
                    self._inst(State="Running", Step="chạy kịch bản")
                    ok, ctx = self.svc.run(dev, self._report, self.cfg.get("account_timeout_sec", 900))
                    status = "Done" if ok else "Error"
                    err = ctx.get("error", "")
        except Exception as e:
            status, err = "Error", f"{type(e).__name__}: {e}"
            self.logger.debug(traceback.format_exc())

        shot = ""
        if status != "Done":
            shot = self._screenshot(dev, u)
        final_step = "xong" if status == "Done" else (ctx.get("screen") or self._last_screen or stage)
        self.store.update_account(u, Status=status, Step=final_step, DurationSec=round(time.time() - t0),
                                  Claimed=ctx.get("claimed", 0), Equipped=ctx.get("equipped", 0),
                                  Error=err[:300], Screenshot=shot)
        self._inst(State="Done" if status == "Done" else "Error", Step=f"{u}: {status}")
        self._log("INFO" if status == "Done" else "ERROR", f"Kết thúc acc {u}: {status}" + (f" - {err}" if err else ""))
        if status == "Done":
            self.done += 1
        else:
            self.failed += 1

    def _screenshot(self, dev, username) -> str:
        try:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            p = SHOT_DIR / f"{username}_{time.strftime('%H%M%S')}.png"
            cv2.imwrite(str(p), dev.screen())
            return str(p)
        except Exception:
            return ""
