### Purpose

- Convert images acquired with an MD ImageXpress HCS.ai microscope to an OME-Zarr Plate.

### Outputs

- An OME-Zarr Plate.

### Limitations

- This task has been tested on a limited set of acquisitions. It may not work on all MD ImageXpress acquisitions.

### Expected inputs

The following directory structure is expected:

```text
experiment{_mode}/
├── {acquisition_name}.jdce
├── image_metadata_1.csv
├── timepoint0/
└── timepoint1/
    ├── {protocol_name}_t1_C05_s0_w0_z0.tif
    ├── {protocol_name}_t1_C05_s0_w0_z1.tif
    └── ...
```

`Path` should point to the `experiment{_mode}` folder.
Depending on what options are chosen during acquisition, multiple experiment folders can appear. The tested cases are:
- Default: If only stacks / only projections / only single planes are saved, a single folder appears:
    - `experiment`
- If both stacks and projections or single planes are stored, two folders appear:
    - `experiment`: contains the projection or single plane data
    - `experiment_z_stack`: contains the full z-stack data
- If the montage or stitching functionality is used, also two folders appear:
    - `experiment`: contains the unstitched tiles (usually preferred for use in Fractal)
    - `experiment_montage` contains the stitched / montaged images
