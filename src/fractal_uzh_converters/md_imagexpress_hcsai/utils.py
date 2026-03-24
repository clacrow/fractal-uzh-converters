"""Utility functions for MD ImageXpress HCS.ai data."""

import json
import logging
from pathlib import Path

import pandas as pd
import polars
from ome_zarr_converters_tools import (
    AcquisitionDetails,
    AcquisitionOptions,
    ChannelInfo,
    ConverterOptions,
    TiledImage,
    default_axes_builder,
    join_url_paths,
    tiles_aggregation_pipeline,
)
from ome_zarr_converters_tools.core import hcs_images_from_dataframe
from pydantic import BaseModel, Field, field_validator

from fractal_uzh_converters.md_imagexpress_hcsai.color_utils import (
    wavelength_to_default_color,
)

logger = logging.getLogger(__name__)


######################################################################
#
# Acquisition Input Model
#
######################################################################


class MDAcquisitionOptions(AcquisitionOptions):
    """Acquisition options for conversion.

    Attributes:
        channels: List of channel information.
        pixel_info: Pixel size information.
        condition_table_path: Optional path to a condition table CSV file.
        axes: Axes to use for the image data, e.g. "czyx".
        data_type: Data type of the image data.
        stage_corrections: Stage orientation corrections.
        filters: List of filters to apply.
        convert_only_projections: If True, only convert projection images, if available.
        convert_montages: If True, convert montaged / stitched images, if available.
    """

    convert_only_projections: bool = Field(default=False)
    convert_montages: bool = Field(default=False)


class MDImageXpressHCSaiAcquisitionModel(BaseModel):
    """Acquisition details for the MD ImageXpress HCS.ai microscope data.

    Attributes:
        path: Path to the *.mxprotocol file or the folder containing it.
        plate_name: Optional custom name for the plate. If not provided, the name will
            be the acquisition directory name.
        acquisition_id: Acquisition ID,
            used to identify the acquisition in case of multiple acquisitions.
        convert_only_projections: If True, only convert projection images, if available.
        convert_montages: If True, convert montaged / stitched images, if available.
        advanced: Advanced acquisition options.
    """

    path: str
    plate_name: str | None = None
    acquisition_id: int = Field(default=0, ge=0)
    advanced: MDAcquisitionOptions = Field(default_factory=MDAcquisitionOptions)

    @property
    def normalized_plate_name(self) -> str:
        """Get the normalized plate name."""
        if self.plate_name is not None:
            return self.plate_name
        name = self.path.rstrip("/").split("/")[-1]
        return name

    def get_condition_table(self) -> polars.DataFrame | None:
        """Get the path to the condition table if it exists."""
        if self.advanced.condition_table_path is not None:
            try:
                return polars.read_csv(self.advanced.condition_table_path)
            except Exception as e:
                raise ValueError(
                    "Failed to read condition table at "
                    f"{self.advanced.condition_table_path}: {e}"
                ) from e
        return None

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Make the path more flexible.

        Allow:
         - path/to/acquisition/{protocol}.mxprotocol
         - path/to/acquisition/
        """
        v = v.rstrip("/")
        if v.endswith(".mxprotocol"):
            # Strip the filename to get the directory
            return str(Path(v).parent)
        return v


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
    # using the field offsets instead of the stage positions, as they are more robust
    # and consistent across wells
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
    acquisition_model: MDImageXpressHCSaiAcquisitionModel,
    converter_options: ConverterOptions,
) -> list[TiledImage]:
    """Parse MD ImageXpress HCS.ai metadata and return a list of TiledImages.

    Args:
        acquisition_model: Acquisition input model containing path and options.
        converter_options: Converter options for tile processing.

    Returns:
        List of TiledImage objects ready for conversion.
    """
    root_dir = acquisition_model.path

    # Discover available experiment directories
    available_dirs = {
        "montage": list(Path(root_dir).glob("experiment_montage")),
        "z_stack": list(Path(root_dir).glob("experiment_z_stack")),
        "standard": list(Path(root_dir).glob("experiment")),
    }

    # Check if any experiment directories exist
    if not any(available_dirs.values()):
        raise FileNotFoundError(
            f"No 'experiment*' folders found in {root_dir}. Please ensure the path is "
            "correct and contains the expected folder structure."
        )

    # Select the appropriate directory based on conversion options
    if acquisition_model.advanced.convert_montages:
        # convert_montages==True -> look for 'experiment_montage' folder
        if not available_dirs["montage"]:
            available = [k for k, v in available_dirs.items() if v]
            raise FileNotFoundError(
                f"No 'experiment_montage' folder found in {root_dir} for montages. "
                f"Available folders: {available}. "
                "Hint: Disable the 'convert_montages' option."
            )
        experiment_dir = available_dirs["montage"][0]
    elif not acquisition_model.advanced.convert_only_projections:
        # convert_montages==False & convert_only_projections==False
        # -> prefer 'experiment_z_stack', fall back to 'experiment'
        if available_dirs["z_stack"]:
            experiment_dir = available_dirs["z_stack"][0]
        elif available_dirs["standard"]:
            experiment_dir = available_dirs["standard"][0]
        else:
            available = [k for k, v in available_dirs.items() if v]
            raise FileNotFoundError(
                f"No 'experiment_z_stack' or 'experiment' folder found in {root_dir}. "
                f"Available folders: {available}."
            )
    else:
        # convert_only_projections==True
        # -> look for 'experiment' folder (projections are stored there)
        if not available_dirs["standard"]:
            available = [k for k, v in available_dirs.items() if v]
            raise FileNotFoundError(
                f"No 'experiment' folder found in {root_dir} for projections. "
                f"Available folders: {available}. "
                "Hint: Disable the 'convert_only_projections' option."
            )
        experiment_dir = available_dirs["standard"][0]

    # TODO: handle condition table
    condition_table = acquisition_model.get_condition_table()
    if condition_table:
        raise NotImplementedError("Condition tables are not yet supported.")

    # Load channel metadata from .jdce file
    jdce_files = sorted(Path(experiment_dir).glob("*.jdce"))
    if len(jdce_files) == 0:
        raise FileNotFoundError(f"No .jdce file found in directory: {experiment_dir}")
    elif len(jdce_files) > 1:
        raise ValueError(
            f"Multiple .jdce files found in directory: {experiment_dir}."
            "Please ensure there is only one .jdce file."
        )
    else:
        jdce_file = jdce_files[0]
    channel_metadata = parse_jdce_metadata(jdce_file)

    # Load image list from .csv file
    csv_files = sorted(Path(experiment_dir).glob("*.csv"))
    if len(csv_files) == 0:
        raise FileNotFoundError(f"No .csv file found in directory: {experiment_dir}")
    elif len(csv_files) > 1:
        raise ValueError(
            f"Multiple .csv files found in directory: {experiment_dir}."
            "Please ensure there is only one .csv file."
        )
    else:
        csv_file = csv_files[0]
    df_csv = load_csv_metadata(csv_file)

    # Determine if data is a z-stack by checking for multiple Z indices
    is_z_stack = df_csv["ZIndex"].nunique() > 1

    # Check if data is compatible with projection and montage conversion options
    if (
        acquisition_model.advanced.convert_only_projections
        and acquisition_model.advanced.convert_montages
        and is_z_stack
    ):
        raise ValueError(
            "Both convert_only_projections and convert_montages are True, but the "
            "montage-data is a z-stack. "
            "Hint: Set either convert_only_projections or convert_montages to False."
        )

    # Build tiles table
    tiles_table = construct_tiles_table(df_csv, str(experiment_dir))

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
        plate_name=acquisition_model.normalized_plate_name,
        acquisition_id=acquisition_model.acquisition_id,
    )

    # Build TiledImages
    tiled_images = tiles_aggregation_pipeline(
        tiles=tiles,
        converter_options=converter_options,
    )

    return tiled_images
