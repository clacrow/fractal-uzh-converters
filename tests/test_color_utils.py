import pytest
from ome_zarr_converters_tools.models._acquisition import DefaultColors

from fractal_uzh_converters.md_imagexpress_hcsai.color_utils import (
    wavelength_to_default_color,
)


@pytest.mark.parametrize(
    "wavelength, expected_color",
    [
        # UV -> magenta
        (300, DefaultColors.magenta),
        (350, DefaultColors.magenta),
        # Violet/Blue
        (380, DefaultColors.blue),
        (405, DefaultColors.blue),
        (449, DefaultColors.blue),
        # Cyan
        (450, DefaultColors.cyan),
        (488, DefaultColors.cyan),
        # Green
        (495, DefaultColors.green),
        (510, DefaultColors.green),
        # Lime
        (520, DefaultColors.lime),
        (540, DefaultColors.lime),
        # Yellow
        (560, DefaultColors.yellow),
        (575, DefaultColors.yellow),
        # Orange
        (590, DefaultColors.orange),
        (610, DefaultColors.orange),
        # Red
        (620, DefaultColors.red),
        (680, DefaultColors.red),
        (749, DefaultColors.red),
        # Far red/IR -> magenta
        (750, DefaultColors.magenta),
        (800, DefaultColors.magenta),
    ],
)
def test_wavelength_to_default_color(
    wavelength: float, expected_color: DefaultColors
):
    assert wavelength_to_default_color(wavelength) == expected_color
