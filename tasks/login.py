"""Màn hình đầu: bấm 'Vào Game'."""


def enter_game(dev, timeout=60) -> bool:
    """Chờ màn hình chọn server (có nút Vào Game) rồi bấm. True nếu bấm được."""
    dev.log.info("Chờ màn hình đăng nhập...")
    ok = dev.wait_and_click("btn_vao_game", timeout=timeout)
    if ok:
        dev.log.info("Đã bấm Vào Game")
    return ok
