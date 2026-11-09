"""Chạy nhiều acc cùng lúc trên nhiều tab LDPlayer, trạng thái ghi vào Excel.

  py manager.py              chạy các acc Pending
  py manager.py --retry      chạy cả acc Error / LoginFailed
  py manager.py --limit 8    chỉ chạy 8 acc đầu
  py manager.py --tabs 1,2   chỉ dùng tab LDPlayer 1 và 2
"""
import argparse
import json
import logging
import queue
import random
import sys
import threading
from pathlib import Path

from core.excel_store import ExcelStore, build_template
from worker import AccountWorker, Services

ROOT = Path(__file__).resolve().parent


def load_cfg(path=None) -> dict:
    return json.loads(Path(path or ROOT / "config.json").read_text(encoding="utf-8"))


def default_services(cfg, store) -> Services:
    from core.device import Device
    from core.ldplayer import LDPlayer
    from tasks import account_login, runner
    ld = LDPlayer(cfg["ld_console"], cfg["adb_path"])
    pkg = cfg["package"]
    return Services(
        ld, store,
        make_device=lambda serial: Device(serial),
        restart_game=lambda dev: account_login.restart_game(dev, pkg, cfg.get("game_start_timeout_sec", 120)),
        login=lambda dev, u, p, sv: account_login.switch_account(dev, u, p, sv),
        run=lambda dev, report, timeout: runner.run(dev, report=report, timeout=timeout),
    )


def run_manager(cfg, store, svc, args) -> dict:
    """Điều phối. Trả về {'done': n, 'failed': n, 'total': n}."""
    store.normalize_and_recover()
    statuses = list(cfg.get("process_statuses", ["Pending"]))
    if args.retry:
        statuses += list(cfg.get("retry_statuses", ["Error", "LoginFailed"]))
    accounts = store.load_accounts(statuses)
    if args.limit:
        accounts = accounts[: args.limit]
    if not accounts:
        print("Không có acc nào cần chạy (Enabled=Y và Status thuộc %s)." % statuses)
        return {"done": 0, "failed": 0, "total": 0}

    tabs = [int(t) for t in args.tabs.split(",")] if args.tabs else list(cfg["instance_indexes"])
    tabs = tabs[: min(cfg.get("max_parallel", 4), len(accounts))]
    print(f"Sẽ chạy {len(accounts)} acc trên {len(tabs)} tab LDPlayer: {tabs}")

    q = queue.Queue()
    for a in accounts:
        q.put(a)
    stop = threading.Event()
    lo, hi = cfg.get("stagger_sec", [5, 20])
    workers = [AccountWorker(t, q, svc, cfg, stop, start_delay=0 if i == 0 else random.uniform(lo, hi) * i)
               for i, t in enumerate(tabs)]

    store.start()
    for w in workers:
        w.start()
    try:
        while any(w.is_alive() for w in workers):
            for w in workers:
                w.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\nNhận Ctrl+C -> dừng sau acc hiện tại...")
        stop.set()
        for w in workers:
            w.join(timeout=60)
    finally:
        # acc còn kẹt 'Running' do bị ngắt -> trả về Pending để lần sau chạy lại
        while not q.empty():
            q.get_nowait()
        store.stop()
        store.normalize_and_recover()
    return {"done": sum(w.done for w in workers), "failed": sum(w.failed for w in workers), "total": len(accounts)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retry", action="store_true", help="chạy cả acc Error/LoginFailed")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tabs", default="", help="vd 1,2,3")
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    cfg = load_cfg(args.config)
    xlsx = ROOT / cfg.get("accounts_file", "accounts.xlsx")
    if not xlsx.exists():
        build_template(xlsx)
        print(f"Chưa có {xlsx.name} -> đã tạo file mẫu. Điền acc vào sheet Accounts rồi chạy lại.")
        return
    if not cfg.get("package"):
        sys.exit('Chưa điền "package" trong config.json. Chạy: py tools/find_package.py emulator-5556')

    store = ExcelStore(xlsx)
    svc = default_services(cfg, store)
    res = run_manager(cfg, store, svc, args)
    print(f"XONG: {res['done']} OK, {res['failed']} lỗi / {res['total']} acc. Xem kết quả trong {xlsx.name}")


if __name__ == "__main__":
    main()