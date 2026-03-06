"""Color utility functions."""

from ome_zarr_converters_tools.models._acquisition import DefaultColors


def wavelength_to_default_color(wavelength: float) -> DefaultColors:
    """Map wavelength (nm) to the closest DefaultColors enum value.

    Args:
        wavelength: Wavelength in nanometers (nm)

    Returns:
        The closest matching DefaultColors enum value
    """
    # Map wavelength ranges to DefaultColors based on visible spectrum
    if wavelength < 380:  # UV -> magenta
        return DefaultColors.magenta
    elif wavelength < 450:  # Violet/Blue
        return DefaultColors.blue
    elif wavelength < 495:  # Cyan
        return DefaultColors.cyan
    elif wavelength < 520:  # Green
        return DefaultColors.green
    elif wavelength < 560:  # Lime/Yellow-green
        return DefaultColors.lime
    elif wavelength < 590:  # Yellow
        return DefaultColors.yellow
    elif wavelength < 620:  # Orange
        return DefaultColors.orange
    elif wavelength < 750:  # Red
        return DefaultColors.red
    else:  # Far red/IR -> magenta
        return DefaultColors.magenta


# class WavelengthColor:
#     """Color for the channel, based on wavelength."""

#     def __init__(self, wavelength: float):
#         """Initialize the WavelengthColor with a wavelength in nm.

#         Args:
#             wavelength: Wavelength in nanometers (nm)
#         """
#         self.wavelength = wavelength
#         self._hex = self._wavelength_to_hex(wavelength)

#     def to_hex(self) -> str:
#         """Convert the color to hex format."""
#         return self._hex

#     def _wavelength_to_hex(self, wavelength: float) -> str:
#         """Convert wavelength (in nm) to an RGB hex color string.

#         Approximates the screen color of a wavelength (380-780 nm) inspired by
#         Bruton's algorithm. Below 380 nm it returns magenta, above 780 nm it
#         returns white.
#         (https://www.eureca.de/5116-1-Bruton-color-mapping.html)

#         Args:
#             wavelength: Wavelength in nanometers (nm)

#         Returns:
#             RGB hex color string (e.g., "#RRGGBB")
#         """
#         if wavelength < 380:
#             R = 1.0
#             G = 0.0
#             B = 1.0
#         elif 380 <= wavelength < 440:
#             R = -(wavelength - 440) / (440 - 380)
#             G = 0.0
#             B = 1.0
#         elif 440 <= wavelength < 490:
#             R = 0.0
#             G = (wavelength - 440) / (490 - 440)
#             B = 1.0
#         elif 490 <= wavelength < 510:
#             R = 0.0
#             G = 1.0
#             B = -(wavelength - 510) / (510 - 490)
#         elif 510 <= wavelength < 580:
#             R = (wavelength - 510) / (580 - 510)
#             G = 1.0
#             B = 0.0
#         elif 580 <= wavelength < 645:
#             R = 1.0
#             G = -(wavelength - 645) / (645 - 580)
#             B = 0.0
#         elif 645 <= wavelength <= 780:
#             R = 1.0
#             G = -(wavelength - 780) / (780 - 645)
#             B = -(wavelength - 780) / (780 - 645)
#         else:  # wavelength > 780
#             R = 1.0
#             G = 1.0
#             B = 1.0

#         def adjust(c):
#             return round(c * 255)

#         r, g, b = adjust(R), adjust(G), adjust(B)
#         return f"#{r:02x}{g:02x}{b:02x}"
