"""Chạy thử trên 1 instance: py main.py emulator-5556"""
import logging
import sys
 
from core.device import Device, CFG
from tasks.runner import run
 
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
 
if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else CFG["serials"][0]
    dev = Device(serial)
    w, h = dev.adb.size()
    dev.log.info("Độ phân giải thiết bị: %dx%d", w, h)
    ok = run(dev)
    dev.log.info("KẾT QUẢ: %s", "THÀNH CÔNG" if ok else "THẤT BẠI")