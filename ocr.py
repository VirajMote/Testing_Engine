# ocr.py — Image preprocessing + Tesseract OCR extraction

import os
import tempfile
from pathlib import Path
from typing import Union

import cv2
import numpy as np
import pytesseract
from PIL import Image


def _preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    Apply a sequence of preprocessing steps to improve OCR accuracy:
      1. Convert to grayscale
      2. Upscale if image is too small (Tesseract works best at 300 DPI+)
      3. Denoise
      4. Adaptive thresholding (handles uneven lighting)
      5. Deskew (straighten rotated receipts)
    """
    # 1. Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    # 2. Upscale if small
    h, w = gray.shape
    if max(h, w) < 1000:
        scale = 1000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 3. Denoise
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # 4. Adaptive threshold — handles shadows and uneven lighting
    gray = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )

    # 5. Deskew
    gray = _deskew(gray)

    return gray


def _deskew(img: np.ndarray) -> np.ndarray:
    """Detect and correct skew angle using Hough line transform."""
    try:
        coords = np.column_stack(np.where(img > 0))
        if len(coords) < 10:
            return img
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
        if abs(angle) < 0.5:
            return img  # skip tiny corrections
        (h, w) = img.shape
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated
    except Exception:
        return img  # deskew is best-effort; never block the pipeline


def _load_image_from_file(file_path: str) -> list[np.ndarray]:
    """
    Load one or more images from a file path.
    Supports: JPEG, PNG, BMP, TIFF, WEBP, PDF.
    Returns a list of numpy arrays (one per page for PDFs).
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _load_pdf_pages(file_path)

    # Standard image formats
    pil_img = Image.open(file_path).convert("RGB")
    return [np.array(pil_img)]


def _load_pdf_pages(file_path: str) -> list[np.ndarray]:
    """Convert each PDF page to an image using pdf2image (poppler)."""
    try:
        from pdf2image import convert_from_path
        pages = convert_from_path(file_path, dpi=300)
        return [np.array(p.convert("RGB")) for p in pages]
    except ImportError:
        raise RuntimeError(
            "pdf2image is required for PDF support. "
            "Install it with: pip install pdf2image"
        )
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF to images: {e}")


def extract_text(file_path: str) -> str:
    """
    Main entry point.
    Accepts an image or PDF path, preprocesses each page/image,
    runs Tesseract OCR, and returns the combined raw text.
    """
    images = _load_image_from_file(file_path)

    all_text: list[str] = []
    for img in images:
        preprocessed = _preprocess_image(img)

        # --psm 6 = assume a single uniform block of text (good for receipts)
        # --oem 3 = default LSTM engine
        custom_config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(preprocessed, config=custom_config)
        all_text.append(text)

    return "\n".join(all_text)
