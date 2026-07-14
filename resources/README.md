# Resources

This directory is for deploy-time assets that travel with the pipeline but are not ordinary source code.

Expected layout:

```text
resources/
  models/
    nnUNet/
    moAR-diff/
  templates/
  licenses/
```

Large model/template files should generally stay out of git. The code resolves nnU-Net Task523 from:

```text
resources/models/nnUNet/nnUNetData
```

During transition, `scripts/jobs/nnunet_task523.sh` also accepts the older sibling layout via `NNUNET_RESOURCE_DIR`.

The current denoise model boundary points at:

```text
resources/models/moAR-diff/CBCP_UnDPM_with_age_finetune
```

The preprocessing workflow can select and stage questionable/fail subjects before the moAR-diff command itself is finalized.
