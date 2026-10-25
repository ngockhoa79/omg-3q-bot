"""Trang bị tướng: Đội Hình -> dấu cộng ở ô trống -> Nhấp Thêm -> chọn tướng -> Ra trận."""
import time

from core import vision
from tasks.hanh_thuong import back_to_event_main

REGION_LBL_DOI_HINH = (0, 640, 230, 720)   # nhãn 'Đội Hình' ở góc dưới trái màn chính sự kiện
ICON_OFFSET_DH = (0, -40)                  # bấm vào icon (phía trên nhãn)
REGION_TITLE_DH = (100, 0, 300, 56)
REGION_SLOTS = (0, 90, 170, 640)           # cột ô tướng bên trái
REGION_NHAP_THEM = (400, 380, 900, 560)
MAX_ACTIONS = 8                            # số thao tác tối đa trong màn Đội Hình mỗi lượt chạy

# Tướng muốn ra trận theo giai đoạn (template tên tướng trong danh sách 'Thay Tướng').
# TODO: bổ sung tướng cho từng giai đoạn; hiện tạm dùng Tôn Sách cho tất cả.
HEROES_BY_STAGE = {
    "lt160":   ["row_ton_sach"],     # level < 160
    "160_180": ["row_ton_sach"],     # 160 <= level < 180
    "ge180":   ["row_ton_sach"],     # level >= 180
}


def get_stage(dev, ctx) -> str:
    """Xác định giai đoạn theo level. TODO: đọc level thật từ màn hình; tạm mặc định lt160."""
    return ctx.get("stage", "lt160")


def target_heroes(dev, ctx):
    return HEROES_BY_STAGE[get_stage(dev, ctx)]


# ===== Từ màn chính sự kiện =====
def open_doi_hinh(dev, timeout=6) -> bool:
    """Bấm 'Đội Hình' ở màn chính sự kiện và chờ màn Đội Hình hiện ra."""
    lbl = dev.find("lbl_doi_hinh", REGION_LBL_DOI_HINH)
    if not lbl:
        dev.log.warning("Không thấy nút Đội Hình")
        return False
    dev.log.info("Mở Đội Hình")
    dev.tap(lbl[0] + ICON_OFFSET_DH[0], lbl[1] + ICON_OFFSET_DH[1])
    return dev.wait_for("scr_doi_hinh", timeout=timeout, region=REGION_TITLE_DH) is not None


# ===== Màn hình Đội Hình =====
def handle_doi_hinh_screen(dev, ctx) -> None:
    """Một lượt xử lý ở màn Đội Hình (mỗi lượt đúng 1 thao tác):
    đang ở ô trống có 'Nhấp Thêm' -> bấm;  có dấu cộng -> bấm;  không còn ô trống -> quay lại."""
    ctx["dh_actions"] = ctx.get("dh_actions", 0) + 1
    if ctx["dh_actions"] > MAX_ACTIONS:
        dev.log.warning("Quá %d thao tác ở Đội Hình, thoát", MAX_ACTIONS)
        ctx["dh_done"] = True
        back_to_event_main(dev)
        return

    hit = dev.find("txt_nhap_them", REGION_NHAP_THEM)
    if hit:
        dev.log.info("Bấm 'Nhấp Thêm'")
        dev.tap(hit[0], hit[1])
        time.sleep(1.0)
        return

    plus = dev.find("icon_slot_cong", REGION_SLOTS)
    if plus:
        dev.log.info("Có ô trống đã mở khóa, bấm dấu cộng")
        dev.tap(plus[0], plus[1])
        dev.wait_for("txt_nhap_them", timeout=4, region=REGION_NHAP_THEM)
        return

    dev.log.info("Không còn ô trống để trang bị -> quay lại")
    ctx["dh_done"] = True
    back_to_event_main(dev)


# ===== Popup 'Thay Tướng' =====
def handle_thay_tuong_popup(dev, ctx) -> bool:
    """Chọn tướng mục tiêu và nhấn 'Ra trận'; nếu chỉ có một nút trong popup thì dùng làm fallback."""
    from core import screens

    screen = dev.screen()
    row = None
    for tpl in target_heroes(dev, ctx):
        row = vision.find_scaled(screen, tpl, 0.75)
        if row:
            dev.log.info(
                "Thấy tướng %s trong danh sách (điểm %.2f, tỉ lệ %.2f)",
                tpl, row[2], row[3],
            )
            break

    # Popup Thay Tướng nằm phía trên màn hình; giới hạn vùng để tránh khớp nút ở nền.
    region_popup_rows = (300, 70, 1000, 360)
    btns = vision.find_all(screen, "btn_ra_tran", 0.75, region=region_popup_rows)
    if not btns:
        # Nếu template được crop ở tỉ lệ khác, thử dò đa tỉ lệ.
        button = vision.find_scaled(
            screen, "btn_ra_tran", 0.72, region=region_popup_rows
        )
        if button:
            btns = [(button[0], button[1], button[2])]

    button = None
    if row:
        _, row_y, _, scale = row
        # Ưu tiên nút Ra trận cùng hàng với tướng đã chọn.
        same_row = [
            candidate for candidate in btns
            if -30 <= candidate[1] - row_y <= 130
        ]
        if same_row:
            button = min(
                same_row,
                key=lambda candidate: abs(candidate[1] - row_y - 66),
            )

    # Ảnh hiện tại chỉ có một tướng trong popup. Nếu template hàng tướng không
    # khớp nhưng chỉ có một nút Ra trận, vẫn có thể chọn an toàn nút duy nhất đó.
    if button is None and len(btns) == 1:
        button = btns[0]
        dev.log.warning(
            "Không ghép được hàng tướng với nút; dùng nút Ra trận duy nhất trong popup"
        )

    if button is None:
        path = screens.save_unknown(dev, screen)
        dev.log.error(
            "Không xác định được nút Ra trận an toàn (tìm thấy %d nút); đã lưu ảnh: %s",
            len(btns), path,
        )
        return False

    bx, by, score = button
    dev.log.info("Nhấn Ra trận tại (%d, %d), điểm khớp %.2f", bx, by, score)
    dev.tap(bx, by)

    # Chỉ xác nhận thành công khi popup thực sự biến mất.
    deadline = time.time() + 8
    while time.time() < deadline:
        time.sleep(0.5)
        if screens.detect(dev) != "thay_tuong":
            ctx["equipped"] = ctx.get("equipped", 0) + 1
            dev.log.info("Đã xác minh popup Thay Tướng đóng sau khi nhấn Ra trận")
            return True

    dev.log.error("Đã nhấn Ra trận nhưng popup vẫn còn; lưu ảnh để debug: %s",
                  screens.save_unknown(dev))
    return False
