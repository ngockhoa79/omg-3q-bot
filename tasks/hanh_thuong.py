"""Sự kiện Cỗ Máy Thời Gian -> Hành Thương -> tab Quà -> nhận thưởng miễn phí mỗi ngày."""
import time

# --- vùng / tọa độ (màn hình chuẩn 1280x720) ---
REGION_LBL_HT = (900, 120, 1130, 170)     # nhãn 'Hành Thương' trên màn chính sự kiện
DOT_OFFSET_HT = (10, -80, 60, -30)        # vùng chấm đỏ so với tâm nhãn: (dx1, dy1, dx2, dy2)
ICON_OFFSET_HT = (0, -38)                 # bấm vào icon (phía trên nhãn)
REGION_QUA_DOT = (1222, 295, 1272, 342)   # chấm đỏ trên tab 'Quà'
QUA_TAB_POS = (1228, 377)                 # tâm tab 'Quà'
REGION_NHAN = (600, 140, 1280, 480)       # nút 'Nhận'
REGION_BACK = (0, 0, 160, 80)             # mũi tên quay lại ở góc trên trái


# ===== Màn chính sự kiện =====
def hanh_thuong_red_dot(dev):
    """Chấm đỏ trên icon Hành Thương -> (x,y) hoặc None."""
    lbl = dev.find("lbl_hanh_thuong", REGION_LBL_HT)
    if not lbl:
        dev.log.warning("Không thấy nhãn Hành Thương")
        return None
    cx, cy = lbl[0], lbl[1]
    dx1, dy1, dx2, dy2 = DOT_OFFSET_HT
    return dev.red_dot((cx + dx1, cy + dy1, cx + dx2, cy + dy2))


def open_hanh_thuong(dev, timeout=6) -> bool:
    """Bấm icon Hành Thương và chờ màn hình Hành Thương hiện ra."""
    lbl = dev.find("lbl_hanh_thuong", REGION_LBL_HT)
    if not lbl:
        return False
    dev.log.info("Mở Hành Thương")
    dev.tap(lbl[0] + ICON_OFFSET_HT[0], lbl[1] + ICON_OFFSET_HT[1])
    return dev.wait_for("scr_hanh_thuong", timeout=timeout, region=(100, 10, 260, 66)) is not None


def handle_event_main(dev, ctx) -> bool:
    """Ở màn chính sự kiện. Trả về True nếu đã xong (không còn gì để nhận)."""
    if ctx.get("ht_visits", 0) >= 2:
        dev.log.warning("Đã vào Hành Thương 2 lần, dừng để tránh lặp")
        return True
    if not hanh_thuong_red_dot(dev):
        dev.log.info("Hành Thương không còn chấm đỏ -> xong")
        return True
    ctx["ht_visits"] = ctx.get("ht_visits", 0) + 1
    ctx["qua_clicks"] = 0
    open_hanh_thuong(dev)
    return False


# ===== Màn hình Hành Thương =====
def qua_tab_red_dot(dev):
    return dev.red_dot(REGION_QUA_DOT)


def open_qua_tab(dev) -> bool:
    """Bấm tab 'Quà' rồi chờ nút Nhận hiện."""
    dev.log.info("Mở tab Quà")
    dev.tap(*QUA_TAB_POS)
    return dev.wait_for("btn_nhan", timeout=4, region=REGION_NHAN) is not None


def claim_free_gift(dev) -> bool:
    """Bấm nút 'Nhận' (thưởng miễn phí mỗi ngày)."""
    ok = dev.click("btn_nhan", REGION_NHAN)
    if ok:
        dev.log.info("Đã bấm Nhận")
        time.sleep(1.5)
    return ok


def back_to_event_main(dev, timeout=6) -> bool:
    """Bấm mũi tên quay lại và chờ về màn chính sự kiện."""
    dev.log.info("Quay lại màn chính sự kiện")
    if not dev.click("btn_back_arrow", REGION_BACK):
        dev.tap(45, 35)    # dự phòng
    return dev.wait_for("scr_co_may_thoi_gian", timeout=timeout, region=(0, 170, 130, 290)) is not None


def handle_hanh_thuong_screen(dev, ctx) -> None:
    """Một lượt xử lý ở màn hình Hành Thương:
    có nút Nhận -> nhận;  chưa mở tab Quà mà Quà có chấm đỏ -> mở tab;  không còn gì -> quay lại."""
    if claim_free_gift(dev):
        ctx["claimed"] = ctx.get("claimed", 0) + 1
        return
    if qua_tab_red_dot(dev) and ctx.get("qua_clicks", 0) < 2:
        ctx["qua_clicks"] = ctx.get("qua_clicks", 0) + 1
        if open_qua_tab(dev):
            claim_free_gift(dev)
            ctx["claimed"] = ctx.get("claimed", 0) + 1
        return
    back_to_event_main(dev)
