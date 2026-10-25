"""Các bước ở màn hình chính (home)."""

# Vùng tìm kiếm (x1, y1, x2, y2) trên màn hình 1280x720 để nhanh và ít nhầm hơn
REGION_BANNER_BTN = (600, 560, 1000, 713)     # nút "Đến" nằm dưới cùng của banner


def wait_main_screen(dev, timeout=90) -> bool:
    """STEP 1: chờ vào được màn hình chính (thấy thanh TL/vàng ở trên cùng)."""
    dev.log.info("Chờ vào màn hình chính...")
    ok = dev.wait_for("marker_man_hinh_chinh", timeout=timeout) is not None
    if not ok:
        dev.log.error("Không vào được màn hình chính")
    return ok


def wait_event_banner(dev, timeout=4):
    """STEP 2: chờ ngắn xem banner sự kiện có bật lên không. Trả về (x,y,score) hoặc None."""
    return dev.wait_for("btn_den", timeout=timeout, region=REGION_BANNER_BTN)
