"""Các popup/màn hình phụ có thể bật lên bất cứ lúc nào."""
import time

REGION_TAP_CLOSE = (300, 640, 980, 720)   # dòng chữ 'Nhấn vào vùng trống để tắt đi'
REGION_DONG_Y = (450, 590, 850, 700)      # nút 'Đồng ý' của popup THÔNG BÁO
REGION_THONG_BAO = (480, 0, 800, 70)


def close_tap_blank_popup(dev, timeout=6) -> bool:
    """Popup sự kiện: bấm vào dòng chữ 'Nhấn vào vùng trống để tắt đi' (nằm ngoài khung popup)."""
    hit = dev.find("txt_nhan_vung_trong", REGION_TAP_CLOSE)
    if not hit:
        return False
    dev.log.info("Đóng popup (bấm vùng trống)")
    dev.tap(hit[0], hit[1])
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.7)
        if not dev.exists("txt_nhan_vung_trong", REGION_TAP_CLOSE):
            return True
    dev.log.warning("Bấm rồi nhưng popup vẫn còn")
    return False


def accept_announcement(dev, timeout=6) -> bool:
    """Popup THÔNG BÁO: bấm 'Đồng ý' và chờ popup biến mất."""
    if not dev.click("btn_dong_y", REGION_DONG_Y):
        return False
    dev.log.info("Đã bấm Đồng ý ở THÔNG BÁO")
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.7)
        if not dev.exists("scr_thong_bao", REGION_THONG_BAO):
            return True
    dev.log.warning("Bấm Đồng ý nhưng THÔNG BÁO vẫn còn")
    return False


def launch_from_android_home(dev) -> bool:
    """Đang ở màn hình Android (game đã thoát/crash): bấm icon OMG 3Q để mở lại."""
    if not dev.click("icon_omg3q_launcher", threshold=0.8):
        return False
    dev.log.info("Đã bấm icon OMG 3Q để mở lại game")
    time.sleep(3)
    return True