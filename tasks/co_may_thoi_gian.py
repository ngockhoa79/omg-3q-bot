"""Mở sự kiện Cỗ Máy Thời Gian: 2 đường vào (banner hoặc icon ở home)."""
import time

from core import screens
from tasks.home import wait_main_screen, wait_event_banner

ARRIVED_SCREENS = ("time_machine", "hero_select", "popup_tap_close")


def go_via_banner(dev, banner_hit) -> None:
    """STEP 3A: có banner -> bấm nút 'Đến'."""
    dev.log.info("Có banner, bấm 'Đến'")
    dev.tap(banner_hit[0], banner_hit[1])


def go_via_home_icon(dev) -> bool:
    """STEP 3B: không có banner -> bấm icon 'Cỗ Máy Thời Gian' ở home."""
    dev.log.info("Không có banner, bấm icon Cỗ Máy Thời Gian")
    return dev.click("icon_co_may_thoi_gian")


def confirm_arrived(dev, timeout=10) -> bool:
    """STEP 4: xác nhận đã rời home và vào sự kiện (màn chính sự kiện, hoặc màn hình/popup lần đầu)."""
    end = time.time() + timeout
    while time.time() < end:
        if screens.detect(dev) in ARRIVED_SCREENS:
            return True
        time.sleep(0.7)
    dev.log.error("Không xác nhận được đã vào Cỗ Máy Thời Gian")
    return False


def open_time_machine(dev) -> bool:
    """Luồng chính: vào Cỗ Máy Thời Gian bất kể có banner hay không."""
    if not wait_main_screen(dev):
        return False

    banner = wait_event_banner(dev, timeout=4)   # PHẢI kiểm tra banner trước icon
    if banner:
        go_via_banner(dev, banner)
    elif not go_via_home_icon(dev):
        dev.log.error("Không thấy icon Cỗ Máy Thời Gian")
        return False

    return confirm_arrived(dev)