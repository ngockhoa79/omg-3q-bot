"""Đọc/ghi Excel cho quản lý nhiều acc.

- Nhiều worker (thread) cùng báo trạng thái -> mọi thao tác ghi được xếp hàng đợi,
  một luồng nền gộp lại rồi ghi file 1 lần mỗi vài giây (không bao giờ nhiều luồng cùng mở file).
- Nếu file đang mở trong Excel (Windows khoá file) -> giữ lại hàng đợi, tự thử lại ở lần sau.
- Acc được xác định theo cột Username (không theo số dòng) nên bạn sắp xếp/chèn dòng khi bot chạy cũng không sao.
"""
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

log = logging.getLogger("excel")

SHEET_SUMMARY, SHEET_ACC, SHEET_INST, SHEET_LOG, SHEET_HELP = "Tong_quan", "Accounts", "Instances", "Log", "Huong_dan"

# (tên cột, độ rộng, là cột NHẬP TAY?, mô tả hiện trong comment của tiêu đề)
ACC_COLUMNS = [
    ("STT",         6,  True,  "Số thứ tự (tuỳ chọn, bot không dùng)."),
    ("Username",    22, True,  "Tên tài khoản đăng nhập. PHẢI duy nhất, bot nhận diện acc theo cột này."),
    ("Password",    22, True,  "Mật khẩu. Lưu dạng chữ thường trong file -> đừng chia sẻ file này."),
    ("Server",      14, True,  "Server muốn vào (vd S940). Có thể để trống."),
    ("Enabled",     10, True,  "Y = cho bot chạy acc này, N = bỏ qua."),
    ("Status",      14, False, "Bot ghi: Pending / Running / Done / Error / LoginFailed / Skipped. Muốn chạy lại thì đổi về Pending."),
    ("Step",        20, False, "Bước/màn hình bot đang ở (hoặc bước cuối cùng)."),
    ("Instance",    10, False, "Số tab LDPlayer (index) đã chạy acc này."),
    ("LastRun",     20, False, "Thời điểm bắt đầu chạy gần nhất."),
    ("DurationSec", 12, False, "Thời gian chạy (giây)."),
    ("Claimed",     10, False, "Số lần bấm Nhận quà Hành Thương."),
    ("Equipped",    10, False, "Số tướng đã cho ra trận."),
    ("Error",       45, False, "Lý do lỗi (nếu có)."),
    ("Screenshot",  34, False, "Đường dẫn ảnh chụp màn hình lúc lỗi."),
    ("Note",        26, True,  "Ghi chú của bạn."),
]
ACC_HEADERS = [c[0] for c in ACC_COLUMNS]
STATUSES = ["Pending", "Running", "Done", "Error", "LoginFailed", "Skipped"]

INST_COLUMNS = [("Tab", 8), ("Serial", 18), ("Account", 22), ("Screen", 18), ("Step", 24), ("State", 12), ("Updated", 20), ("Since", 20)]
INST_STATES = ["Idle", "Starting", "LoggingIn", "Running", "Done", "Error", "Stopped"]
LOG_COLUMNS = [("Time", 20), ("Tab", 8), ("Account", 22), ("Level", 10), ("Message", 90)]

FONT = "Arial"
MAX_ROWS = 500          # số dòng acc tối đa các công thức/validation bao phủ
LOG_MAX = 5000          # quá số dòng này thì xoá bớt các dòng cũ nhất


@dataclass
class Account:
    username: str
    password: str
    server: str = ""
    status: str = "Pending"


def _f(bold=False, color="000000", size=10):
    return Font(name=FONT, size=size, bold=bold, color=color)


YELLOW = PatternFill("solid", start_color="FFFF00", end_color="FFFF00")
GREY = PatternFill("solid", start_color="D9D9D9", end_color="D9D9D9")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _fill(hex_color):
    return PatternFill("solid", start_color=hex_color, end_color=hex_color)


# =====================================================================
# Tạo file mẫu
# =====================================================================
def build_template(path) -> None:
    wb = Workbook()

    # ---------------- Accounts ----------------
    ws = wb.active
    ws.title = SHEET_ACC
    for i, (name, width, is_input, desc) in enumerate(ACC_COLUMNS, start=1):
        c = ws.cell(row=1, column=i, value=name)
        c.font = _f(bold=True)
        c.fill = YELLOW if is_input else GREY
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
        c.comment = Comment(("[NHẬP TAY] " if is_input else "[BOT GHI] ") + desc, "bot")
        ws.column_dimensions[c.column_letter].width = width
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(ACC_COLUMNS)).column_letter}{MAX_ROWS}"

    example = {"STT": 1, "Username": "vi_du_acc01", "Password": "vi_du_matkhau", "Server": "S940",
               "Enabled": "N", "Status": "Pending",
               "Note": "VÍ DỤ - thay bằng acc thật rồi đổi Enabled thành Y (acc mẫu này bị bỏ qua)"}
    for r in range(2, MAX_ROWS + 1):
        for i, (name, _, is_input, _) in enumerate(ACC_COLUMNS, start=1):
            c = ws.cell(row=r, column=i)
            c.font = _f(color="0000FF" if is_input else "000000")
            c.border = BORDER
            if name in ("STT", "Instance", "DurationSec", "Claimed", "Equipped"):
                c.alignment = Alignment(horizontal="center")
            if name == "LastRun":
                c.number_format = "yyyy-mm-dd hh:mm:ss"
            if r == 2 and name in example:
                c.value = example[name]

    dv_en = DataValidation(type="list", formula1='"Y,N"', allow_blank=True, showErrorMessage=True,
                           errorTitle="Enabled", error="Chỉ nhập Y hoặc N")
    dv_st = DataValidation(type="list", formula1='"' + ",".join(STATUSES) + '"', allow_blank=True,
                           showErrorMessage=True, errorTitle="Status", error="Chọn một trạng thái trong danh sách")
    ws.add_data_validation(dv_en)
    ws.add_data_validation(dv_st)
    dv_en.add(f"E2:E{MAX_ROWS}")
    dv_st.add(f"F2:F{MAX_ROWS}")

    rng = f"F2:F{MAX_ROWS}"
    for text, color in [("Done", "C6EFCE"), ("Running", "BDD7EE"), ("Error", "FFC7CE"),
                        ("LoginFailed", "F8CBAD"), ("Skipped", "E7E6E6")]:
        ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=[f'"{text}"'], fill=_fill(color)))

    # ---------------- Instances (trạng thái trực tiếp từng tab) ----------------
    wi = wb.create_sheet(SHEET_INST)
    for i, (name, width) in enumerate(INST_COLUMNS, start=1):
        c = wi.cell(row=1, column=i, value=name)
        c.font, c.fill, c.border = _f(bold=True), GREY, BORDER
        c.alignment = Alignment(horizontal="center")
        wi.column_dimensions[c.column_letter].width = width
    wi.freeze_panes = "A2"
    for r in range(2, 21):
        for i in range(1, len(INST_COLUMNS) + 1):
            c = wi.cell(row=r, column=i)
            c.font, c.border = _f(), BORDER
            if INST_COLUMNS[i - 1][0] in ("Updated", "Since"):
                c.number_format = "yyyy-mm-dd hh:mm:ss"
    for text, color in [("Running", "BDD7EE"), ("LoggingIn", "FFF2CC"), ("Starting", "FFF2CC"),
                        ("Done", "C6EFCE"), ("Error", "FFC7CE")]:
        wi.conditional_formatting.add("F2:F20", CellIsRule(operator="equal", formula=[f'"{text}"'], fill=_fill(color)))

    # ---------------- Log ----------------
    wl = wb.create_sheet(SHEET_LOG)
    for i, (name, width) in enumerate(LOG_COLUMNS, start=1):
        c = wl.cell(row=1, column=i, value=name)
        c.font, c.fill, c.border = _f(bold=True), GREY, BORDER
        wl.column_dimensions[c.column_letter].width = width
    wl.freeze_panes = "A2"

    # ---------------- Tong_quan (công thức) ----------------
    wsu = wb.create_sheet(SHEET_SUMMARY, 0)
    wsu["A1"] = "TỔNG QUAN - OMG 3Q bot"
    wsu["A1"].font = _f(bold=True, size=14)
    wsu.column_dimensions["A"].width = 38
    wsu.column_dimensions["B"].width = 14
    wsu.column_dimensions["C"].width = 60
    acc = f"{SHEET_ACC}!"
    E, F = f"{acc}$E$2:$E${MAX_ROWS}", f"{acc}$F$2:$F${MAX_ROWS}"
    ST = f"{SHEET_INST}!$F$2:$F$20"
    rows = [
        ("Tổng số acc (có Username)",     f"=COUNTA({acc}$B$2:$B${MAX_ROWS})", "Đếm cột Username"),
        ("Acc đang bật (Enabled = Y)",    f'=COUNTIF({E},"Y")', ""),
        ("  - Pending (chưa chạy)",       f'=COUNTIFS({E},"Y",{F},"Pending")', ""),
        ("  - Running (đang chạy)",       f'=COUNTIFS({E},"Y",{F},"Running")', ""),
        ("  - Done (xong)",               f'=COUNTIFS({E},"Y",{F},"Done")', ""),
        ("  - Error (lỗi)",               f'=COUNTIFS({E},"Y",{F},"Error")', ""),
        ("  - LoginFailed (login lỗi)",   f'=COUNTIFS({E},"Y",{F},"LoginFailed")', ""),
        ("Tỉ lệ hoàn thành",              "=IFERROR(B7/B4,0)", "Done chia cho số acc đang bật"),
        ("Số tab đang hoạt động",         f'=COUNTIF({ST},"Running")+COUNTIF({ST},"LoggingIn")+COUNTIF({ST},"Starting")', "Running + LoggingIn + Starting"),
        ("Tổng lần nhận quà Hành Thương", f"=SUM({acc}$K$2:$K${MAX_ROWS})", ""),
        ("Tổng tướng đã ra trận",         f"=SUM({acc}$L$2:$L${MAX_ROWS})", ""),
    ]
    for i, (label, formula, note) in enumerate(rows, start=3):
        wsu.cell(row=i, column=1, value=label).font = _f(bold=not label.startswith("  "))
        v = wsu.cell(row=i, column=2, value=formula)
        v.font = _f()
        v.alignment = Alignment(horizontal="center")
        wsu.cell(row=i, column=3, value=note).font = _f(color="7F7F7F")
        if label == "Tỉ lệ hoàn thành":
            v.number_format = "0.0%"
    wsu["A15"] = "Số liệu ở đây tự tính từ sheet Accounts và Instances - không nhập tay."
    wsu["A15"].font = _f(color="7F7F7F")

    # ---------------- Huong_dan ----------------
    wh = wb.create_sheet(SHEET_HELP)
    wh.column_dimensions["A"].width = 26
    wh.column_dimensions["B"].width = 100
    lines = [
        ("HƯỚNG DẪN", None),
        ("Màu tiêu đề (sheet Accounts)", None),
        ("  Vàng", "Cột BẠN NHẬP: STT, Username, Password, Server, Enabled, Note (chữ xanh dương)."),
        ("  Xám", "Cột BOT GHI: Status, Step, Instance, LastRun, DurationSec, Claimed, Equipped, Error, Screenshot - đừng sửa tay (trừ Status khi muốn chạy lại)."),
        ("Quy tắc", None),
        ("  Username", "Phải duy nhất. Bot tìm acc theo cột này, nên bạn có thể sắp xếp/lọc dòng thoải mái."),
        ("  Enabled", "Y = chạy, N = bỏ qua. Dòng ví dụ ở hàng 2 đang để N - thay bằng acc thật rồi đổi thành Y."),
        ("  Status", "Để trống hoặc Pending = chờ chạy. Muốn chạy lại acc nào thì đổi Status về Pending."),
        ("  Chạy hằng ngày", "Chạy:  py tools/reset_status.py  để đưa tất cả acc đang bật về Pending, rồi chạy:  py manager.py"),
        ("Lưu ý khi bot đang chạy", None),
        ("  Đang mở file", "Bot ghi file mỗi vài giây. Nếu file đang mở trong Excel, Windows khoá file -> bot giữ lại và tự ghi bù khi bạn đóng file. Để xem trạng thái, đóng rồi mở lại file."),
        ("  Bảo mật", "Mật khẩu lưu dạng chữ thường. Không gửi/chia sẻ file này."),
        ("Các sheet", None),
        ("  Tong_quan", "Thống kê tự tính (công thức)."),
        ("  Accounts", "Danh sách acc + kết quả từng acc."),
        ("  Instances", "Trạng thái trực tiếp từng tab LDPlayer: acc đang chạy, màn hình hiện tại, trạng thái."),
        ("  Log", "Nhật ký sự kiện (tự xoá bớt dòng cũ khi quá 5000 dòng)."),
        ("Trạng thái Status", "Pending, Running, Done, Error, LoginFailed, Skipped"),
        ("Trạng thái tab (State)", "Idle, Starting, LoggingIn, Running, Done, Error, Stopped"),
    ]
    for i, (a, b) in enumerate(lines, start=1):
        ca = wh.cell(row=i, column=1, value=a)
        ca.font = _f(bold=(b is None))
        if b:
            cb = wh.cell(row=i, column=2, value=b)
            cb.font = _f()
            cb.alignment = Alignment(wrap_text=True, vertical="top")
    wh["A1"].font = _f(bold=True, size=14)

    wb.save(str(path))


# =====================================================================
# Store
# =====================================================================
class ExcelStore:
    def __init__(self, path, flush_interval: float = 3.0):
        self.path = Path(path)
        self.flush_interval = flush_interval
        self._pending = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._warned_locked = False

    # ---------- đọc ----------
    def _open(self, **kw):
        return load_workbook(str(self.path), **kw)

    @staticmethod
    def _header_map(ws) -> dict:
        return {str(c.value).strip(): c.column for c in ws[1] if c.value is not None}

    def load_accounts(self, statuses=("Pending",)):
        """Danh sách acc cần chạy: Enabled = Y, có Username/Password, Status thuộc `statuses` (trống = Pending)."""
        wb = self._open()
        ws = wb[SHEET_ACC]
        h = self._header_map(ws)
        missing = [n for n in ("Username", "Password", "Enabled", "Status") if n not in h]
        if missing:
            raise ValueError(f"Sheet Accounts thiếu cột: {missing}")
        out, seen = [], set()
        for r in range(2, ws.max_row + 1):
            u = ws.cell(row=r, column=h["Username"]).value
            if u is None or str(u).strip() == "":
                continue
            u = str(u).strip()
            if u in seen:
                log.warning("Username trùng: %s (dòng %d) - bỏ qua dòng này", u, r)
                continue
            seen.add(u)
            if str(ws.cell(row=r, column=h["Enabled"]).value or "").strip().upper() != "Y":
                continue
            st = str(ws.cell(row=r, column=h["Status"]).value or "").strip() or "Pending"
            if st not in statuses:
                continue
            pw = ws.cell(row=r, column=h["Password"]).value
            if pw is None or str(pw) == "":
                log.warning("Acc %s chưa có Password - bỏ qua", u)
                continue
            sv = ws.cell(row=r, column=h["Server"]).value if "Server" in h else ""
            out.append(Account(u, str(pw), str(sv or "").strip(), st))
        return out

    # ---------- ghi (xếp hàng đợi) ----------
    def update_account(self, username: str, **fields):
        with self._lock:
            self._pending.append(("acc", username, fields))

    def update_instance(self, tab, **fields):
        with self._lock:
            self._pending.append(("inst", tab, fields))

    def add_log(self, tab, account, level, message):
        with self._lock:
            self._pending.append(("log", (datetime.now(), tab, account, level, message), None))

    # ---------- ghi xuống file ----------
    def flush(self) -> bool:
        with self._lock:
            batch = list(self._pending)
        if not batch:
            return True
        tmp = self.path.with_name(self.path.stem + ".tmp" + self.path.suffix)
        try:
            wb = self._open()
            self._apply(wb, batch)
            wb.save(str(tmp))
            os.replace(tmp, self.path)
        except (PermissionError, OSError) as e:
            if not self._warned_locked:
                log.warning("Không ghi được %s (đang mở trong Excel?). Giữ lại %d thay đổi, sẽ thử lại. (%s)",
                            self.path.name, len(batch), e)
                self._warned_locked = True
            try:
                tmp.unlink()
            except OSError:
                pass
            return False
        self._warned_locked = False
        with self._lock:
            del self._pending[:len(batch)]
        return True

    def _apply(self, wb, batch):
        ws, wi, wl = wb[SHEET_ACC], wb[SHEET_INST], wb[SHEET_LOG]
        ha = self._header_map(ws)
        hi = self._header_map(wi)
        user_row = {}
        for r in range(2, ws.max_row + 1):
            v = ws.cell(row=r, column=ha["Username"]).value
            if v is not None and str(v).strip() != "":
                user_row.setdefault(str(v).strip(), r)
        tab_row = {}
        for r in range(2, wi.max_row + 1):
            v = wi.cell(row=r, column=hi["Tab"]).value
            if v is not None and str(v) != "":
                tab_row[str(v)] = r

        for kind, key, fields in batch:
            if kind == "acc":
                r = user_row.get(key)
                if r is None:
                    log.warning("Không tìm thấy acc %s trong Excel để cập nhật", key)
                    continue
                for name, val in fields.items():
                    if name in ha:
                        ws.cell(row=r, column=ha[name], value=val)
            elif kind == "inst":
                r = tab_row.get(str(key))
                if r is None:
                    r = max(tab_row.values(), default=1) + 1
                    tab_row[str(key)] = r
                    wi.cell(row=r, column=hi["Tab"], value=key)
                for name, val in fields.items():
                    if name in hi:
                        wi.cell(row=r, column=hi[name], value=val)
            elif kind == "log":
                wl.append(list(key))
        if wl.max_row > LOG_MAX:
            wl.delete_rows(2, wl.max_row - LOG_MAX + 1000)

    # ---------- luồng nền ----------
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="excel-flush", daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(self.flush_interval):
            self.flush()

    def stop(self, wait_sec: float = 30) -> bool:
        """Dừng luồng nền và ghi nốt phần còn lại (thử lại tới wait_sec giây nếu file đang bị khoá)."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        end = time.time() + wait_sec
        while not self.flush():
            if time.time() > end:
                log.error("Không ghi nốt được Excel (file đang mở?). Còn %d thay đổi chưa lưu.", len(self._pending))
                return False
            time.sleep(1)
        return True

    # ---------- tiện ích ----------
    def normalize_and_recover(self) -> int:
        """Khi khởi động: trạng thái trống -> Pending; 'Running' sót từ lần chạy bị ngắt -> Pending."""
        wb = self._open()
        ws = wb[SHEET_ACC]
        h = self._header_map(ws)
        changed = 0
        for r in range(2, ws.max_row + 1):
            u = ws.cell(row=r, column=h["Username"]).value
            if u is None or str(u).strip() == "":
                continue
            c = ws.cell(row=r, column=h["Status"])
            if (c.value in (None, "")) or c.value == "Running":
                c.value = "Pending"
                changed += 1
        if changed:
            wb.save(str(self.path))
            log.info("Đã chuẩn hoá %d dòng về Pending", changed)
        return changed

    def reset_statuses(self, only_enabled=True) -> int:
        """Đưa acc về Pending và xoá cột kết quả (dùng cho lượt chạy mới mỗi ngày)."""
        wb = self._open()
        ws = wb[SHEET_ACC]
        h = self._header_map(ws)
        clear = ["Step", "Instance", "LastRun", "DurationSec", "Claimed", "Equipped", "Error", "Screenshot"]
        n = 0
        for r in range(2, ws.max_row + 1):
            u = ws.cell(row=r, column=h["Username"]).value
            if u is None or str(u).strip() == "":
                continue
            if only_enabled and str(ws.cell(row=r, column=h["Enabled"]).value or "").strip().upper() != "Y":
                continue
            ws.cell(row=r, column=h["Status"], value="Pending")
            for name in clear:
                if name in h:
                    ws.cell(row=r, column=h[name], value=None)
            n += 1
        wb.save(str(self.path))
        return n
