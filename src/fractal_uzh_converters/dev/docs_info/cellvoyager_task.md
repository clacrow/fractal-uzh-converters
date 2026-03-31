### Purpose

- Convert images acquired with a Yokogawa CellVoyager microscope to an OME-Zarr Plate.

### Outputs

- An OME-Zarr Plate.

### Limitations

- This task has been tested on a limited set of acquisitions. It may not work on all Yokogawa CellVoyager acquisitions.
- Unlike the CQ3K converter, this task does not support Z-image processing types (e.g., `focus`, `maximum_projection`).

### Expected inputs

The following directory structure is expected:

```text
my_acquisition/
├── MeasurementData.mlf      # Image measurement records (required)
├── MeasurementDetail.mrf    # Acquisition details and channel info (required)
├── image_001.png
└── ...
```

The image file paths are referenced inside `MeasurementData.mlf` (with `.tif` extension) and can be in subdirectories relative to the acquisition directory. The actual files may use `.png` or `.tif` extension — select the matching extension via the `image_extension` parameter.
