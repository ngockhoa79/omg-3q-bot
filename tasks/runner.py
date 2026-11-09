"""Vòng lặp chính cho 1 acc: mỗi vòng nhận diện màn hình hiện tại rồi chạy đúng handler.

run(dev, report=None, timeout=None) -> (ok, ctx)
  report(screen_name, ctx): hàm gọi mỗi vòng để báo trạng thái (dùng cho Excel/Instances)
  timeout: số giây tối đa cho 1 acc
  ctx: dict kết quả: claimed, equipped, error, note ...
"""
import logging
import time

from core import screens
from tasks.login import enter_game
from tasks.co_may_thoi_gian import open_time_machine
from tasks.chon_tuong import select_ton_sach
from tasks.popup import close_tap_blank_popup, accept_announcement, launch_from_android_home
from tasks.hanh_thuong import handle_event_main, handle_hanh_thuong_screen
from tasks.doi_hinh import open_doi_hinh, handle_doi_hinh_screen, handle_thay_tuong_popup

MAX_STEPS = 60          # tối đa số vòng, tránh chạy vô hạn
MAX_UNKNOWN = 8         # số lần liên tiếp không nhận ra màn hình thì dừng
MAX_SAME = 6            # cùng 1 màn hình mà xử lý quá số lần này vẫn không đổi -> coi là kẹt


def run(dev, report=None, timeout=None):
    log = logging.getLogger(dev.serial)
    ctx = {}            # kết quả + trạng thái chung giữa các màn hình
    unknown = 0
    same = 0
    last = None
    progress = False    # đã làm xong ít nhất 1 bước có thật
    t_end = time.time() + timeout if timeout else None

    def fail(msg):
        ctx["error"] = msg
        log.error(msg)
        return False, ctx

    for step in range(1, MAX_STEPS + 1):
        if t_end and time.time() > t_end:
            return fail(f"Quá thời gian {timeout}s cho 1 acc")

        name = screens.detect(dev)
        ctx["screen"] = name
        if report:
            report(name, ctx)
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
                    ctx["note"] = "Màn hình kế tiếp chưa được định nghĩa"
                    log.info("Đã xong các bước đã biết. Màn hình kế tiếp chưa được định nghĩa "
                             "(xem ảnh trong thư mục logs/)")
                    return True, ctx
                return fail(f"Không nhận ra màn hình quá {MAX_UNKNOWN} lần")
            time.sleep(2)
            continue
        unknown = 0

        # --- chống kẹt ---
        same += 1
        if same > MAX_SAME:
            screens.save_unknown(dev)
            return fail(f"Kẹt ở màn hình '{name}' (đã xử lý {MAX_SAME} lần không đổi)")

        # --- xử lý theo màn hình ---
        if name == "login":
            enter_game(dev)
        elif name == "thong_bao":
            accept_announcement(dev)
        elif name == "android_home":
            launch_from_android_home(dev)         # game bị thoát -> mở lại
        elif name == "popup_tap_close":
            if close_tap_blank_popup(dev):
                progress = True
        elif name in ("home", "banner"):
            open_time_machine(dev)            # tự xử lý banner / icon
        elif name == "hero_select":
            if not select_ton_sach(dev):
                return fail("Không chọn được tướng Tôn Sách ở màn hình chọn tướng")
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
                return True, ctx
        elif name == "hanh_thuong":
            handle_hanh_thuong_screen(dev, ctx)
            progress = True
        elif name == "doi_hinh":
            handle_doi_hinh_screen(dev, ctx)
            progress = True
        elif name == "thay_tuong":
            if not handle_thay_tuong_popup(dev, ctx):
                return fail("Không chọn được tướng trong popup Thay Tướng")
            progress = True
        time.sleep(1)

    return fail(f"Hết {MAX_STEPS} bước mà chưa xong")