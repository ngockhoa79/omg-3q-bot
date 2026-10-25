"""Vòng lặp chính: mỗi vòng nhận diện màn hình hiện tại rồi chạy đúng handler."""
import logging
import time

from core import screens
from tasks.login import enter_game
from tasks.co_may_thoi_gian import open_time_machine
from tasks.chon_tuong import select_ton_sach
from tasks.popup import close_tap_blank_popup
from tasks.hanh_thuong import handle_event_main, handle_hanh_thuong_screen
from tasks.doi_hinh import open_doi_hinh, handle_doi_hinh_screen, handle_thay_tuong_popup

MAX_STEPS = 60          # tối đa số vòng, tránh chạy vô hạn
MAX_UNKNOWN = 8         # số lần liên tiếp không nhận ra màn hình thì dừng
MAX_SAME = 6            # cùng 1 màn hình mà xử lý quá số lần này vẫn không đổi -> coi là kẹt


def run(dev) -> bool:
    log = logging.getLogger(dev.serial)
    unknown = 0
    same = 0
    last = None
    progress = False    # đã làm xong ít nhất 1 bước có thật
    ctx = {}            # trạng thái chung giữa các màn hình (số lần vào Hành Thương, đã nhận...)

    for step in range(1, MAX_STEPS + 1):
        name = screens.detect(dev)
        if name != last:
            log.info("[bước %d] Màn hình hiện tại: %s", step, name)
            same = 0
            last = name

        # --- không nhận ra màn hình ---
        if name == "unknown":
            unknown += 1
            if unknown == 1 or unknown % 4 == 0:
                log.warning("Không nhận ra màn hình (lần %d), đã lưu ảnh: %s",
                            unknown, screens.save_unknown(dev))
            if unknown >= MAX_UNKNOWN:
                if progress:
                    log.info("Đã xong các bước đã biết. Màn hình kế tiếp chưa được định nghĩa "
                             "(xem ảnh trong thư mục logs/)")
                    return True
                log.error("Không nhận ra màn hình quá %d lần, dừng", MAX_UNKNOWN)
                return False
            time.sleep(2)
            continue
        unknown = 0

        # --- chống kẹt ---
        same += 1
        if same > MAX_SAME:
            log.error("Kẹt ở màn hình '%s' (đã xử lý %d lần không đổi)", name, MAX_SAME)
            screens.save_unknown(dev)
            return False

        # --- xử lý theo màn hình ---
        if name == "login":
            enter_game(dev)
        elif name == "popup_tap_close":
            if close_tap_blank_popup(dev):
                progress = True
        elif name in ("home", "banner"):
            open_time_machine(dev)            # tự xử lý banner / icon
        elif name == "hero_select":
            if not select_ton_sach(dev):
                return False
            progress = True
            log.info("Xong bước chọn tướng Tôn Sách")
        elif name == "time_machine":
            progress = True
            if not ctx.get("ht_done"):                      # 1) nhận quà Hành Thương
                if handle_event_main(dev, ctx):
                    ctx["ht_done"] = True
            elif not ctx.get("dh_done"):                    # 2) trang bị tướng ở Đội Hình
                ctx["dh_visits"] = ctx.get("dh_visits", 0) + 1
                if ctx["dh_visits"] > 2:
                    log.warning("Đã vào Đội Hình 2 lần, bỏ qua")
                    ctx["dh_done"] = True
                else:
                    open_doi_hinh(dev)
            else:
                log.info("Xong Cỗ Máy Thời Gian (đã nhận %d lần, ra trận %d tướng)",
                         ctx.get("claimed", 0), ctx.get("equipped", 0))
                return True
        elif name == "hanh_thuong":
            handle_hanh_thuong_screen(dev, ctx)
            progress = True
        elif name == "doi_hinh":
            handle_doi_hinh_screen(dev, ctx)
            progress = True
        elif name == "thay_tuong":
            if not handle_thay_tuong_popup(dev, ctx):
                return False
            progress = True
        time.sleep(1)

    log.error("Hết %d bước mà chưa xong", MAX_STEPS)
    return False