"""Deterministic raster preprocessing for uploaded floor-plan images.

Load -> grayscale -> denoise -> binarize -> deskew. No AI/vision-model call;
pure OpenCV image processing. Output is a clean, upright binary mask ready
for wall detection (wall_detect.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np


@dataclass
class PreprocessResult:
    mask: np.ndarray        # uint8, 0/255, wall/line pixels = 255 (foreground)
    gray: np.ndarray        # uint8 grayscale, same upright orientation as mask
    rotation_deg: float     # deskew rotation applied (degrees, counter-clockwise positive)
    size_px: tuple[int, int]  # (width, height) of mask/gray


def _binarize(gray: np.ndarray, method: Literal["otsu", "adaptive"] = "otsu") -> np.ndarray:
    if method == "adaptive":
        return cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 35, 10
        )
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return mask


def _deskew_angle_deg(mask: np.ndarray) -> float:
    lines = cv2.HoughLines(mask, 1, np.pi / 180, threshold=150)
    if lines is None:
        return 0.0
    angles = []
    for line in lines[:200]:
        rho, theta = line[0]
        deg = math.degrees(theta) - 90.0
        # fold into [-45, 45) so both near-horizontal and near-vertical walls agree
        deg = ((deg + 45.0) % 90.0) - 45.0
        angles.append(deg)
    if not angles:
        return 0.0
    hist, edges = np.histogram(angles, bins=180, range=(-45.0, 45.0))
    peak_idx = int(np.argmax(hist))
    return float((edges[peak_idx] + edges[peak_idx + 1]) / 2.0)


def preprocess(image_path: Path, binarize_method: str = "otsu") -> PreprocessResult:
    gray_raw = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if gray_raw is None:
        raise ValueError(f"could not read image: {image_path}")

    denoised = cv2.medianBlur(gray_raw, 3)
    mask = _binarize(denoised, binarize_method)  # type: ignore[arg-type]

    angle = _deskew_angle_deg(mask)
    if abs(angle) < 0.3:
        angle = 0.0
        gray_up, mask_up = denoised, mask
    else:
        h, w = mask.shape
        center = (w / 2.0, h / 2.0)
        rot = cv2.getRotationMatrix2D(center, angle, 1.0)
        gray_up = cv2.warpAffine(denoised, rot, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
        mask_up = cv2.warpAffine(mask, rot, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)

    h, w = mask_up.shape
    return PreprocessResult(mask=mask_up, gray=gray_up, rotation_deg=angle, size_px=(w, h))
