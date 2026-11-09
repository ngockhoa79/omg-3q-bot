"""Vòng lặp chính: nhận diện màn hình, chạy handler và chỉ báo thành công khi đã xác minh."""
import logging
import time

from core import screens
from tasks.login import enter_game
from tasks.co_may_thoi_gian import open_time_machine
from tasks.chon_tuong import select_ton_sach
from tasks.popup import close_tap_blank_popup
from tasks.hanh_thuong import handle_event_main, handle_hanh_thuong_screen
from tasks.doi_hinh import open_doi_hinh, handle_doi_hinh_screen, handle_thay_tuong_popup

MAX_STEPS = 60
MAX_UNKNOWN = 8
MAX_SAME = 6


def _wait_for_screen(dev, expected, timeout=6, interval=0.5) -> bool:
    """Chờ màn hình mục tiêu xuất hiện sau thao tác UI."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if screens.detect(dev) == expected:
            return True
        time.sleep(interval)
    return False


def run(dev) -> bool:
    log = logging.getLogger(dev.serial)
    unknown = 0
    same = 0
    last = None
    progress = False
    ctx = {}

    for step in range(1, MAX_STEPS + 1):
        name = screens.detect(dev)
        if name != last:
            log.info("[bước %d] Màn hình hiện tại: %s", step, name)
            same = 0
            last = name

        if name == "unknown":
            unknown += 1
            if unknown == 1 or unknown % 4 == 0:
                log.warning("Không nhận ra màn hình (lần %d), đã lưu ảnh: %s",
                            unknown, screens.save_unknown(dev))
            if unknown >= MAX_UNKNOWN:
                log.error(
                    "Không nhận ra màn hình quá %d lần; không thể xác minh workflow hoàn tất",
                    MAX_UNKNOWN,
                )
                return False
            time.sleep(2)
            continue
        unknown = 0

        same += 1
        if same > MAX_SAME:
            log.error("Kẹt ở màn hình '%s' (đã xử lý %d lần không đổi)", name, MAX_SAME)
            screens.save_unknown(dev)
            return False

        if name == "login":
            enter_game(dev)

        elif name == "popup_tap_close":
            if not close_tap_blank_popup(dev):
                log.warning("Không đóng được popup; sẽ thử lại")
            else:
                progress = True

        elif name in ("home", "banner"):
            if not open_time_machine(dev):
                log.error("Không mở được Cỗ Máy Thời Gian từ màn hình '%s'", name)
                return False

        elif name == "hero_select":
            if not select_ton_sach(dev):
                log.error("Không hoàn tất chọn tướng Tôn Sách")
                return False
            progress = True
            log.info("Xong bước chọn tướng Tôn Sách")

        elif name == "time_machine":
            if not ctx.get("ht_done"):
                if handle_event_main(dev, ctx):
                    ctx["ht_done"] = True
                    progress = True
                elif not _wait_for_screen(dev, "hanh_thuong", timeout=6):
                    log.error("Không mở được màn Hành Thương; dừng thay vì đánh dấu đã hoàn tất")
                    return False

            elif not ctx.get("dh_done"):
                if not open_doi_hinh(dev):
                    log.error("Không mở được màn Đội Hình")
                    return False
                # Chỉ tăng số lượt sau khi đã xác minh màn Đội Hình mở thành công.
                ctx["dh_visits"] = ctx.get("dh_visits", 0) + 1
                progress = True

            else:
                log.info(
                    "Workflow hoàn tất: đã xử lý Hành Thương và xác minh trạng thái Đội Hình "
                    "(đã nhận %d lần, ra trận %d tướng)",
                    ctx.get("claimed", 0), ctx.get("equipped", 0),
                )
                return True

        elif name == "hanh_thuong":
            handle_hanh_thuong_screen(dev, ctx)
            progress = True

        elif name == "doi_hinh":
            handle_doi_hinh_screen(dev, ctx)
            progress = True

        elif name == "thay_tuong":
            if not handle_thay_tuong_popup(dev, ctx):
                log.error("Không hoàn tất thao tác chọn tướng trong popup")
                return False
            progress = True

        time.sleep(1)

    log.error("Hết %d bước mà chưa xác minh workflow hoàn tất (progress=%s)", MAX_STEPS, progress)
    return False
