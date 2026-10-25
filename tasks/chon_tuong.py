"""Màn hình 'Hãy chọn 1 Tướng bất kỳ' (chỉ xuất hiện lần đầu vào Cỗ Máy Thời Gian).
Bấm mũi tên phải cho tới khi tướng ở giữa là Tôn Sách rồi bấm OK."""
import time

REGION_NAME = (380, 330, 640, 390)      # nhãn tên tướng ở giữa
REGION_ARROW = (1100, 380, 1280, 500)   # mũi tên phải
REGION_OK = (450, 590, 830, 700)        # nút OK
ARROW_FALLBACK = (1205, 440)            # tọa độ dự phòng nếu không nhận ra mũi tên
MAX_CLICKS = 8                          # số lần bấm mũi tên tối đa (game có ~4 tướng)
ANIM_WAIT = 1.2                         # chờ hiệu ứng chuyển tướng (giây)
ARROW_THRESHOLD = 0.7                   # nền mũi tên thay đổi theo tướng nên hạ ngưỡng


def is_hero_select_screen(dev, timeout=6) -> bool:
    """STEP 1: có đang ở màn hình chọn tướng không (chờ ngắn vì chỉ hiện lần đầu)."""
    return dev.wait_for("scr_chon_tuong", timeout=timeout, threshold=0.7) is not None


def is_ton_sach_selected(dev) -> bool:
    """STEP 2: tướng đang ở giữa có phải Tôn Sách không (xác nhận 2 lần liên tiếp để tránh bắt nhầm lúc đang chuyển)."""
    if not dev.exists("lbl_ton_sach", REGION_NAME):
        return False
    time.sleep(0.5)
    return dev.exists("lbl_ton_sach", REGION_NAME)


def click_next_arrow(dev) -> None:
    """STEP 3: bấm mũi tên phải để chuyển sang tướng kế tiếp."""
    if not dev.click("btn_mui_ten_phai", REGION_ARROW, threshold=ARROW_THRESHOLD):
        dev.log.warning("Không nhận ra mũi tên, bấm theo tọa độ dự phòng")
        dev.tap(*ARROW_FALLBACK)
    time.sleep(ANIM_WAIT)


def confirm_ok(dev) -> bool:
    """STEP 4: bấm OK để chốt tướng, rồi chờ màn hình chọn tướng biến mất."""
    if not dev.wait_and_click("btn_ok", timeout=5, region=REGION_OK):
        return False
    end = time.time() + 8
    while time.time() < end:
        if not dev.exists("scr_chon_tuong", threshold=0.7):
            return True
        time.sleep(0.7)
    dev.log.error("Bấm OK nhưng màn hình chọn tướng vẫn còn")
    return False


def select_ton_sach(dev) -> bool:
    """Luồng chính. Không có màn hình chọn tướng (đã chọn trước đó) -> bỏ qua, coi như thành công."""
    if not is_hero_select_screen(dev):
        dev.log.info("Không có màn hình chọn tướng, bỏ qua")
        return True

    for i in range(MAX_CLICKS + 1):
        if is_ton_sach_selected(dev):
            dev.log.info("Đã chọn Tôn Sách sau %d lần bấm mũi tên", i)
            return confirm_ok(dev)
        if i < MAX_CLICKS:
            click_next_arrow(dev)

    dev.log.error("Bấm %d lần vẫn không thấy Tôn Sách", MAX_CLICKS)
    return False
