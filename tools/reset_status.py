"""Đưa các acc đang bật (Enabled=Y) về Pending và xoá cột kết quả - dùng cho lượt chạy mới mỗi ngày.
  py tools/reset_status.py"""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.excel_store import ExcelStore

cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
n = ExcelStore(ROOT / cfg.get("accounts_file", "accounts.xlsx")).reset_statuses()
print(f"Đã đưa {n} acc về Pending")
