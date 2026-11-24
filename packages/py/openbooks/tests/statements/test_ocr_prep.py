import math

import pytest

Image = pytest.importorskip("PIL.Image")
np = pytest.importorskip("numpy")

from openbooks.statements.ocr_prep import estimate_skew_degrees, prepare_for_ocr  # noqa: E402

INK_THRESHOLD = 128
LINE_TOP_OFFSET = 30
LINE_SPACING = 45
LINE_HEIGHT = 8
WORD_WIDTH = 18
WORD_PITCH = 30
MARGIN = 40
DEFAULT_BORDER = 10
SIZE_TOLERANCE_PX = 2


def make_text_line_image(width: int = 600, height: int = 400, line_count: int = 8) -> Image.Image:
    canvas = np.full((height, width), 255, dtype=np.uint8)
    for line_index in range(line_count):
        top = LINE_TOP_OFFSET + line_index * LINE_SPACING
        for left in range(MARGIN, width - MARGIN, WORD_PITCH):
            canvas[top : top + LINE_HEIGHT, left : left + WORD_WIDTH] = 0
    return Image.fromarray(canvas, mode="L")


def rotate_white(image: Image.Image, angle_degrees: float) -> Image.Image:
    return image.rotate(angle_degrees, resample=Image.BICUBIC, fillcolor=255)


def ink_row_profile(gray: Image.Image) -> np.ndarray:
    array = np.asarray(gray)
    return (array < INK_THRESHOLD).sum(axis=1)


def ink_row_indices(gray: Image.Image) -> set[int]:
    return set(np.flatnonzero(ink_row_profile(gray) > 0).tolist())


def row_projection_variance(gray: Image.Image) -> float:
    return float(np.var(ink_row_profile(gray).astype(float)))


def test_output_is_grayscale_mode_l():
    rgb = make_text_line_image().convert("RGB")
    result = prepare_for_ocr(rgb, border_px=0)
    assert result.mode == "L"


def test_output_pixels_are_only_pure_black_or_white():
    result = prepare_for_ocr(make_text_line_image(), border_px=0)
    assert set(np.unique(np.asarray(result)).tolist()) <= {0, 255}


def test_output_pixels_are_binary_for_rgb_input():
    rgb = make_text_line_image().convert("RGB")
    result = prepare_for_ocr(rgb, border_px=0)
    assert set(np.unique(np.asarray(result)).tolist()) <= {0, 255}


def test_border_rows_and_columns_are_white_without_source_dpi():
    source = make_text_line_image()
    result = np.asarray(prepare_for_ocr(source, border_px=DEFAULT_BORDER))
    assert np.all(result[:DEFAULT_BORDER, :] == 255)
    assert np.all(result[-DEFAULT_BORDER:, :] == 255)
    assert np.all(result[:, :DEFAULT_BORDER] == 255)
    assert np.all(result[:, -DEFAULT_BORDER:] == 255)


def test_size_grows_by_twice_border_px_without_source_dpi():
    source = make_text_line_image()
    result = prepare_for_ocr(source, border_px=DEFAULT_BORDER)
    assert result.size == (source.width + 2 * DEFAULT_BORDER, source.height + 2 * DEFAULT_BORDER)


def test_rescale_applies_target_over_source_dpi_factor():
    source = make_text_line_image(width=400, height=300)
    result = prepare_for_ocr(source, target_dpi=300, source_dpi=150, border_px=0)
    assert abs(result.width - source.width * 2) <= SIZE_TOLERANCE_PX
    assert abs(result.height - source.height * 2) <= SIZE_TOLERANCE_PX


def test_downscale_applies_target_over_source_dpi_factor():
    source = make_text_line_image(width=600, height=400)
    result = prepare_for_ocr(source, target_dpi=150, source_dpi=300, border_px=0)
    assert abs(result.width - source.width / 2) <= SIZE_TOLERANCE_PX
    assert abs(result.height - source.height / 2) <= SIZE_TOLERANCE_PX


@pytest.mark.parametrize("angle_degrees", [2.0, -3.0])
def test_skew_estimate_matches_rotation_within_half_degree(angle_degrees):
    rotated = rotate_white(make_text_line_image(), angle_degrees)
    estimated = estimate_skew_degrees(np.asarray(rotated))
    assert abs(estimated - angle_degrees) < 0.5


@pytest.mark.parametrize("angle_degrees", [2.0, -3.0])
def test_deskewed_output_has_sharper_row_projection_than_rotated_input(angle_degrees):
    rotated = rotate_white(make_text_line_image(), angle_degrees)
    corrected = prepare_for_ocr(rotated, border_px=0)
    assert row_projection_variance(corrected) > row_projection_variance(rotated)


def test_zero_rotation_keeps_content_rows_in_place():
    source = make_text_line_image()
    result = prepare_for_ocr(source, border_px=0)
    assert result.size == source.size
    assert ink_row_indices(result) == ink_row_indices(source)


def test_two_calls_produce_identical_bytes():
    source = rotate_white(make_text_line_image(), 2.0)
    first = prepare_for_ocr(source, border_px=DEFAULT_BORDER)
    second = prepare_for_ocr(source, border_px=DEFAULT_BORDER)
    assert first.mode == second.mode
    assert first.size == second.size
    assert first.tobytes() == second.tobytes()


def test_input_image_is_not_mutated():
    source = rotate_white(make_text_line_image(), -3.0).convert("RGB")
    before_pixels = np.asarray(source).copy()
    before_mode = source.mode
    before_size = source.size
    prepare_for_ocr(source, target_dpi=300, source_dpi=200, border_px=DEFAULT_BORDER)
    assert source.mode == before_mode
    assert source.size == before_size
    assert np.array_equal(np.asarray(source), before_pixels)


def test_blank_white_image_does_not_crash():
    blank = Image.new("L", (200, 120), 255)
    result = prepare_for_ocr(blank, border_px=DEFAULT_BORDER)
    assert result.mode == "L"
    assert set(np.unique(np.asarray(result)).tolist()) <= {0, 255}


def test_skew_estimate_on_blank_image_is_finite_float():
    estimated = estimate_skew_degrees(np.full((120, 200), 255, dtype=np.uint8))
    assert isinstance(estimated, float)
    assert math.isfinite(estimated)
