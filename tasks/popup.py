"""Các popup chung có thể bật lên bất cứ lúc nào."""
import time

REGION_TAP_CLOSE = (300, 640, 980, 720)   # dòng chữ 'Nhấn vào vùng trống để tắt đi'


def close_tap_blank_popup(dev, timeout=6) -> bool:
    """Popup sự kiện (vd. Di Lăng Chiến): bấm vào dòng chữ 'Nhấn vào vùng trống để tắt đi'
    (nằm ngoài khung popup) để đóng. True nếu popup đã biến mất."""
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
