"""Màn hình đăng nhập chính: tick ô đồng ý (nếu chưa) rồi bấm 'Vào Game'."""
import time

REGION_VAO_GAME = (450, 540, 830, 700)
REGION_CHK = (300, 630, 400, 700)       # ô 'Tôi đã đọc và đồng ý với các...'
CHK_POS = (341, 666)                    # tâm ô tick


def agreement_checked(dev) -> bool:
    return dev.exists("chk_ticked", REGION_CHK)


def ensure_agreement_checked(dev, tries=3) -> bool:
    """Tick ô đồng ý nếu chưa tick. True nếu đã tick."""
    if agreement_checked(dev):
        return True
    for _ in range(tries):
        dev.log.info("Ô đồng ý chưa tick, bấm tick")
        dev.tap(*CHK_POS)
        time.sleep(0.7)
        if agreement_checked(dev):
            return True
    dev.log.error("Không tick được ô đồng ý")
    return False


def enter_game(dev, timeout=60) -> bool:
    """Chờ màn hình đăng nhập, tick ô đồng ý nếu cần rồi bấm Vào Game."""
    dev.log.info("Chờ màn hình đăng nhập...")
    if dev.wait_for("btn_vao_game", timeout=timeout, region=REGION_VAO_GAME) is None:
        dev.log.warning("Không thấy nút Vào Game")
        return False
    if not ensure_agreement_checked(dev):
        return False
    ok = dev.click("btn_vao_game", REGION_VAO_GAME)
    if ok:
        dev.log.info("Đã bấm Vào Game")
    return ok