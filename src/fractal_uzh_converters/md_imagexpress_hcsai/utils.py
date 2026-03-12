"""Utility functions for MD ImageXpress HCS.ai data."""

import json
import logging
from pathlib import Path

import pandas as pd
from ome_zarr_converters_tools import (
    AcquisitionDetails,
    ChannelInfo,
    ConverterOptions,
    TiledImage,
    default_axes_builder,
    join_url_paths,
    tiles_aggregation_pipeline,
)
from ome_zarr_converters_tools.core import hcs_images_from_dataframe

from fractal_uzh_converters.common import (
    BaseAcquisitionModel,
)
from fractal_uzh_converters.md_imagexpress_hcsai.color_utils import (
    wavelength_to_default_color,
)

logger = logging.getLogger(__name__)


######################################################################
#
# Load MD metadata
#
######################################################################


def parse_jdce_metadata(file_path):
    """Parse JDCE metadata file and extract key imaging parameters."""
    with open(file_path) as f:
        data = json.load(f)

    protocol = data["ImageStack"]["AutoLeadAcquisitionProtocol"]

    # Extract pixel sizes
    calib = protocol["ObjectiveCalibration"]
    pixel_width_um = calib["PixelWidth"]
    pixel_height_um = calib["PixelHeight"]

    # Extract z-step information
    z_step_um = protocol["PlateMap"]["ZDimensionParameters"]["Step"]
    if z_step_um == 0.0:
        z_step_um = 1.0

    # Extract image size in pixels
    camera = protocol["Camera"]
    width_px = camera["Size"]["Width"]
    height_px = camera["Size"]["Height"]

    # Calculate image size in µm
    width_um = width_px * pixel_width_um
    height_um = height_px * pixel_height_um

    # Extract channel information
    channels = []
    for wl in protocol["Wavelengths"]:
        channels.append(
            {
                "index": wl["Index"],
                "name": wl["EmissionFilter"]["Name"],
                "emission_wavelength": wl["EmissionFilter"]["Wavelength"],
            }
        )

    timepoints = protocol["PlateMap"]["TimeSchedule"]["Times"]
    if len(timepoints) > 1:
        is_time_series = True
    else:
        is_time_series = False

    return {
        "pixel_size": {
            "width_um": pixel_width_um,
            "height_um": pixel_height_um,
            "unit": "µm",
        },
        "z_step_um": z_step_um,
        "tile_size": {
            "width_px": width_px,
            "height_px": height_px,
            "width_um": width_um,
            "height_um": height_um,
        },
        "channels": channels,
        "objective": calib["ObjectiveName"],
        "binning": camera["Binning"],
        "is_time_series": is_time_series,
        "is_z_stack": z_step_um > 0,
    }


def load_csv_metadata(fn):
    """Load CSV metadata file."""
    df = pd.read_csv(fn)
    return df


def construct_tiles_table(df_csv, acquisition_dir):
    """Construct tiles table from file-dataframe and channel metadata."""
    # construct tiles_table
    tiles_table = pd.DataFrame()
    # Build absolute file paths
    relative_paths = df_csv["ImageSubFolderPath"] + "/" + df_csv["ImageFileName"]
    tiles_table["file_path"] = relative_paths.apply(
        lambda rel_path: join_url_paths(acquisition_dir, rel_path)
    )

    tiles_table["fov_name"] = "FOV" + df_csv["Field"].astype(str)
    # tiles_table["start_x"] = df_csv["PositionXUm"]
    # tiles_table["start_y"] = df_csv["PositionYUm"]
    tiles_table["start_x"] = df_csv["FieldOffsetPointX"]
    tiles_table["start_y"] = df_csv["FieldOffsetPointY"]
    tiles_table["start_z"] = df_csv["ZIndex"]
    tiles_table["start_c"] = df_csv["Wavelength"]
    tiles_table["start_t"] = df_csv["Timepoint"]
    tiles_table["length_x"] = df_csv["ImageSizeXPx"]
    tiles_table["length_y"] = df_csv["ImageSizeYPx"]
    tiles_table["length_z"] = 1
    tiles_table["length_c"] = 1
    tiles_table["length_t"] = 1
    tiles_table["row"] = df_csv["Row"]
    tiles_table["column"] = df_csv["Column"]

    return tiles_table


######################################################################
#
# Main metadata parsing function
#
######################################################################


def parse_md_metadata(
    *,
    acquisition_model: BaseAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse MD ImageXpress HCS.ai metadata and return a list of TiledImages.

    Args:
        acquisition_model: Acquisition input model containing path and options.
        converter_options: Converter options for tile processing.

    Returns:
        List of TiledImage objects ready for conversion.
    """
    acquisition_dir = acquisition_model.path
    # TODO: handle condition table
    condition_table = acquisition_model.get_condition_table()
    if condition_table:
        raise NotImplementedError("Condition tables are not yet supported.")

    # Load channel metadata from .jdce file
    jdce_files = sorted(Path(acquisition_dir).glob("*.jdce"))
    if len(jdce_files) == 0:
        raise FileNotFoundError(f"No .jdce file found in directory: {acquisition_dir}")
    elif len(jdce_files) > 1:
        raise ValueError(
            f"Multiple .jdce files found in directory: {acquisition_dir}."
            "Please ensure there is only one .jdce file."
        )
    else:
        jdce_file = jdce_files[0]
    channel_metadata = parse_jdce_metadata(jdce_file)

    # Load image list from .csv file
    csv_files = sorted(Path(acquisition_dir).glob("*.csv"))
    if len(csv_files) == 0:
        raise FileNotFoundError(f"No .csv file found in directory: {acquisition_dir}")
    elif len(csv_files) > 1:
        raise ValueError(
            f"Multiple .csv files found in directory: {acquisition_dir}."
            "Please ensure there is only one .csv file."
        )
    else:
        csv_file = csv_files[0]
    df_csv = load_csv_metadata(csv_file)

    # Build tiles table
    tiles_table = construct_tiles_table(df_csv, acquisition_dir)

    # Build AcquisitionDetails
    channels = []
    for i, c in enumerate(channel_metadata["channels"]):
        if c["index"] != i:  # sanity check to ensure correct order
            raise ValueError(f"Channel index mismatch: expected {i}, got {c['index']}")
        channels.append(
            ChannelInfo(
                channel_label=c["name"],
                wavelength_id=str(c["emission_wavelength"]),
                colors=wavelength_to_default_color(c["emission_wavelength"]),
            )
        )
    acq = AcquisitionDetails(
        channels=channels,
        pixelsize=channel_metadata["pixel_size"]["width_um"],
        z_spacing=channel_metadata["z_step_um"],  # micrometers
        t_spacing=1.0,  # seconds TODO: extract actual t_spacing
        axes=default_axes_builder(is_time_series=channel_metadata["is_time_series"]),
        # Coordinate systems: start positions are in world coordinates,
        # lengths are in pixel coordinates
        start_x_coo="world",
        start_y_coo="world",
        start_z_coo="pixel",
        start_t_coo="pixel",
        length_x_coo="pixel",
        length_y_coo="pixel",
        length_z_coo="pixel",
        length_t_coo="pixel",
    )

    # Build tiles
    tiles = hcs_images_from_dataframe(
        tiles_table=tiles_table,
        acquisition_details=acq,
        plate_name=acquisition_model.plate_name,
        acquisition_id=acquisition_model.acquisition_id,
    )

    # Build TiledImages
    tiled_images = tiles_aggregation_pipeline(
        tiles=tiles,
        converter_options=converter_options,
        # resource=acquisition_dir,
    )

    return tiled_images
