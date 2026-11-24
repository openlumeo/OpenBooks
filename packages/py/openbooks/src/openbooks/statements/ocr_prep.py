from __future__ import annotations

try:
    import numpy as np
    from PIL import Image, ImageOps
except ImportError as error:
    raise ImportError(
        "OCR image preparation needs numpy and Pillow; install them with openbooks[scan]"
    ) from error

WHITE = 255
SKEW_SIDE_PX = 1000
SKEW_LIMIT_DEGREES = 5.0
SKEW_STEP_DEGREES = 0.25
MIN_CORRECTION_DEGREES = 0.25
BINARISE_RADIUS = 15
BINARISE_OFFSET = 10


def _integral_window_sums(values: np.ndarray, radius: int) -> np.ndarray:
    size = 2 * radius + 1
    padded = np.pad(values, radius, mode="edge")
    integral = np.zeros((padded.shape[0] + 1, padded.shape[1] + 1), dtype=np.int64)
    integral[1:, 1:] = padded.cumsum(axis=0).cumsum(axis=1)
    height, width = values.shape
    return (
        integral[size : size + height, size : size + width]
        - integral[:height, size : size + width]
        - integral[size : size + height, :width]
        + integral[:height, :width]
    )


def _binarise(gray: np.ndarray) -> np.ndarray:
    values = np.asarray(gray, dtype=np.int64)
    window = 2 * BINARISE_RADIUS + 1
    local_mean = _integral_window_sums(values, BINARISE_RADIUS) / (window * window)
    return np.where(values > local_mean - BINARISE_OFFSET, WHITE, 0).astype(np.uint8)


def estimate_skew_degrees(gray: np.ndarray) -> float:
    stride = max(1, max(gray.shape) // SKEW_SIDE_PX)
    small = np.asarray(gray)[::stride, ::stride]
    ink = np.where(_binarise(small) == 0, WHITE, 0).astype(np.uint8)
    if not ink.any():
        return 0.0
    mask = Image.fromarray(ink)
    steps = round(2 * SKEW_LIMIT_DEGREES / SKEW_STEP_DEGREES) + 1
    angles = [-SKEW_LIMIT_DEGREES + index * SKEW_STEP_DEGREES for index in range(steps)]
    scores = []
    for angle in angles:
        rotated = mask.rotate(angle, resample=Image.Resampling.BILINEAR)
        profile = np.asarray(rotated, dtype=np.float64).sum(axis=1)
        scores.append(float(profile.var()))
    best_rotation = angles[int(np.argmax(scores))]
    return -best_rotation


def prepare_for_ocr(
    image: Image.Image,
    *,
    target_dpi: int = 300,
    source_dpi: int | None = None,
    border_px: int = 10,
) -> Image.Image:
    if target_dpi <= 0 or (source_dpi is not None and source_dpi <= 0):
        raise ValueError("DPI values must be positive")
    gray = image.convert("L")
    if source_dpi is not None and source_dpi != target_dpi:
        scale = target_dpi / source_dpi
        size = (round(gray.width * scale), round(gray.height * scale))
        gray = gray.resize(size, Image.Resampling.LANCZOS)
    skew = estimate_skew_degrees(np.asarray(gray))
    if abs(skew) >= MIN_CORRECTION_DEGREES:
        gray = gray.rotate(-skew, resample=Image.Resampling.BILINEAR, fillcolor=WHITE)
    binary = Image.fromarray(_binarise(np.asarray(gray)))
    return ImageOps.expand(binary, border=border_px, fill=WHITE)
