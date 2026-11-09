"""Khởi động lại game và đăng nhập acc ZingID khác.

Luồng: tắt hẳn game -> mở lại -> (THÔNG BÁO: Đồng ý) -> màn đăng nhập -> 'Đổi Tài Khoản' -> ZingID
       -> nhập user/pass -> Đăng nhập -> (THÔNG BÁO: Đồng ý) -> chọn server (nếu có cột Server)
Việc tick ô đồng ý và bấm 'Vào Game' do tasks.login.enter_game đảm nhiệm (runner gọi).
"""
import logging
import time
from pathlib import Path

from core import screens, vision
from tasks.popup import close_tap_blank_popup, accept_announcement, launch_from_android_home

TEMPLATE_DIR = vision.TEMPLATE_DIR

REGION_DOI_TK = (1050, 130, 1280, 240)
REGION_ZINGID = (380, 250, 920, 370)
REGION_ZING_TITLE = (380, 170, 900, 240)
REGION_CHON_SERVER_BTN = (550, 500, 900, 580)

# Vị trí các thành phần form ZingID, tính theo tâm tiêu đề 'Đăng nhập bằng ZingID' (dx, dy)
ZING_OFF_USER = (0, 67)
ZING_OFF_PASS = (0, 139)
ZING_OFF_SUBMIT = (0, 223)

REQUIRED = ["btn_doi_tai_khoan", "btn_zingid", "scr_zing_login"]


def missing_templates(names=REQUIRED):
    return [n for n in names if not (TEMPLATE_DIR / f"{n}.png").exists()]


def _handle_common(dev, name) -> bool:
    """Xử lý các màn hình phụ hay xuất hiện khi khởi động/đăng nhập. True nếu đã xử lý."""
    if name == "thong_bao":
        accept_announcement(dev)
        return True
    if name == "popup_tap_close":
        close_tap_blank_popup(dev)
        return True
    if name == "android_home":
        launch_from_android_home(dev)
        return True
    return False


def restart_game(dev, package: str, timeout: int = 120) -> bool:
    """Tắt hẳn rồi mở lại game, chờ tới màn hình đăng nhập (có nút Vào Game)."""
    log = logging.getLogger(dev.serial)
    dev.adb.force_stop(package)
    time.sleep(2)
    dev.adb.start_app(package)
    log.info("Đã mở game, chờ màn hình đăng nhập...")
    end = time.time() + timeout
    while time.time() < end:
        name = screens.detect(dev)
        if name == "login":
            return True
        if not _handle_common(dev, name):
            time.sleep(2)
    log.error("Không thấy màn hình đăng nhập sau %ds", timeout)
    return False


def _type_into(dev, point, text: str) -> None:
    dev.tap(*point)
    time.sleep(0.6)
    dev.adb.clear_field()
    dev.adb.type_text(text)
    time.sleep(0.4)


def select_server(dev, server: str):
    """Mở bảng 'Chọn server' và bấm đúng server (cần ảnh mẫu templates/servers/<server>.png).
    Chỉ tìm trong tab đang mở (mặc định 'Tập hợp Server' = các server acc đã có nhân vật)."""
    log = logging.getLogger(dev.serial)
    tpl = f"servers/{server}"
    if not (TEMPLATE_DIR / f"{tpl}.png").exists():
        return False, (f"Thiếu ảnh mẫu templates/servers/{server}.png "
                       f"(cắt phần tên server ở bảng Chọn server, bằng tools/crop_template.py)")
    if not dev.click("btn_chon_server", REGION_CHON_SERVER_BTN):
        return False, "Không thấy nút Chọn Server"
    if not dev.wait_for("scr_chon_server", timeout=8, threshold=0.7):
        # tìm lại theo nhiều tỉ lệ
        if not vision.find_scaled(dev.screen(), "scr_chon_server", 0.75):
            return False, "Không mở được bảng Chọn server"
    time.sleep(1)
    hit = vision.find_scaled(dev.screen(), tpl, 0.8)
    if not hit:
        shot = screens.save_unknown(dev)
        return False, f"Không thấy {server} trong tab Tập hợp Server (acc chưa có nhân vật ở server này?). Ảnh: {shot}"
    log.info("Chọn server %s (điểm %.2f)", server, hit[2])
    dev.tap(hit[0], hit[1])
    end = time.time() + 8
    while time.time() < end:
        time.sleep(0.8)
        if screens.detect(dev) != "chon_server":
            return True, ""
    return False, "Bấm chọn server nhưng bảng Chọn server vẫn còn"


def switch_account(dev, username: str, password: str, server: str = ""):
    """Đăng nhập acc ZingID. Trả về (ok, thông báo lỗi). Không bao giờ ghi mật khẩu vào log."""
    log = logging.getLogger(dev.serial)
    miss = missing_templates()
    if miss:
        return False, f"Thiếu template: {miss}"

    # 1) Đổi Tài Khoản -> 2) ZingID
    if not dev.wait_and_click("btn_doi_tai_khoan", timeout=15, region=REGION_DOI_TK):
        return False, "Không thấy nút Đổi Tài Khoản"
    if not dev.wait_and_click("btn_zingid", timeout=15, region=REGION_ZINGID):
        return False, "Không thấy nút ZingID"

    # 3) form đăng nhập
    title = dev.wait_for("scr_zing_login", timeout=15, region=REGION_ZING_TITLE)
    if not title:
        return False, "Không thấy form đăng nhập ZingID"
    tx, ty = title[0], title[1]
    try:
        _type_into(dev, (tx + ZING_OFF_USER[0], ty + ZING_OFF_USER[1]), username)
        _type_into(dev, (tx + ZING_OFF_PASS[0], ty + ZING_OFF_PASS[1]), password)
    except ValueError as e:
        return False, f"Username/Password có ký tự không gõ được: {e}"
    dev.tap(tx + ZING_OFF_SUBMIT[0], ty + ZING_OFF_SUBMIT[1])
    log.info("Đã bấm Đăng nhập, chờ vào màn hình chính của game...")

    # 4) chờ quay về màn hình đăng nhập (có thể có THÔNG BÁO -> Đồng ý)
    end = time.time() + 60
    ok_login = False
    while time.time() < end:
        name = screens.detect(dev)
        if name == "login":
            ok_login = True
            break
        if not _handle_common(dev, name):
            time.sleep(1.5)
    if not ok_login:
        return False, "Đăng nhập xong nhưng không về màn hình Vào Game (sai mật khẩu/cần xác thực?)"

    # 5) chọn server nếu Excel có ghi
    if server:
        ok, err = select_server(dev, server)
        if not ok:
            return False, err
    return True, ""