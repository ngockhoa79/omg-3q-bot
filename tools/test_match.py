"""Test nhận diện offline: python tools/test_match.py anh.png ten_template"""
import sys
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import vision

img = cv2.imread(sys.argv[1])
print(vision.find(img, sys.argv[2], 0.0))
