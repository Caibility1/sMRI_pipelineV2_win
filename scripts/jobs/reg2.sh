#!/usr/bin/env bash
set -uo pipefail

SUBJECT_DIR=${1:?Usage: bash reg2.sh SUBJECT_DIR QC_IMAGE_DIR}
QC_IMAGE_DIR=${2:?Usage: bash reg2.sh SUBJECT_DIR QC_IMAGE_DIR}
FSLDIR=${FSLDIR:?FSLDIR is not set}

if [ ! -d "$SUBJECT_DIR" ]; then
    echo "ERROR: subject directory not found: $SUBJECT_DIR" >&2
    exit 1
fi
if [ ! -x "${FSLDIR}/bin/flirt" ] || [ ! -x "${FSLDIR}/bin/slicer" ] || [ ! -x "${FSLDIR}/bin/pngappend" ]; then
    echo "ERROR: FSL flirt, slicer, or pngappend is unavailable under $FSLDIR/bin" >&2
    exit 1
fi

mkdir -p "$QC_IMAGE_DIR"
SUBJECT_NAME=$(basename "$SUBJECT_DIR")
LOG_FILE="$SUBJECT_DIR/registration_log.txt"
OUTPUT_DIR="$SUBJECT_DIR/registration"
T1_FILE="$SUBJECT_DIR/T1.nii.gz"
T2_FILE="$SUBJECT_DIR/T2.nii.gz"
T2_REGISTERED="$OUTPUT_DIR/T2_to_T1.nii.gz"
TRANSFORM_MATRIX="$OUTPUT_DIR/T2_to_T1.mat"
AXIAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_axial.png"
SAGITTAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_sagittal.png"
CORONAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_coronal.png"
COMBINED_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_combined.png"
OVERLAY_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_overlay.png"

{
    echo "FSL T2 to T1 Registration Log"
    echo "Started at $(date)"
    echo "Subject: $SUBJECT_NAME"
} > "$LOG_FILE"

if [ ! -s "$T1_FILE" ] || [ ! -s "$T2_FILE" ]; then
    echo "Missing T1 or T2; registration skipped" | tee -a "$LOG_FILE"
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
echo "[$SUBJECT_NAME] rigid T2-to-T1 registration started" | tee -a "$LOG_FILE"
if ! "${FSLDIR}/bin/flirt"     -in "$T2_FILE"     -ref "$T1_FILE"     -out "$T2_REGISTERED"     -omat "$TRANSFORM_MATRIX"     -dof 6     -cost mutualinfo     -searchrx -90 90     -searchry -90 90     -searchrz -90 90 >> "$LOG_FILE" 2>&1; then
    echo "[$SUBJECT_NAME] FAILED: FSL flirt returned nonzero" | tee -a "$LOG_FILE" >&2
    exit 1
fi

echo "[$SUBJECT_NAME] registration complete; generating QC montage" | tee -a "$LOG_FILE"
if ! "${FSLDIR}/bin/slicer" "$T1_FILE" "$T2_REGISTERED" -L -t -s 2     -x 0.5 "$SAGITTAL_PNG"     -y 0.5 "$CORONAL_PNG"     -z 0.5 "$AXIAL_PNG"     -a "$OVERLAY_PNG" >> "$LOG_FILE" 2>&1; then
    echo "[$SUBJECT_NAME] FAILED: FSL slicer returned nonzero" | tee -a "$LOG_FILE" >&2
    exit 1
fi
if ! "${FSLDIR}/bin/pngappend"     "$SAGITTAL_PNG" + "$CORONAL_PNG" + "$AXIAL_PNG" "$COMBINED_PNG"     >> "$LOG_FILE" 2>&1; then
    echo "[$SUBJECT_NAME] FAILED: FSL pngappend returned nonzero" | tee -a "$LOG_FILE" >&2
    exit 1
fi

for output in "$T2_REGISTERED" "$TRANSFORM_MATRIX" "$SAGITTAL_PNG" "$CORONAL_PNG" "$AXIAL_PNG" "$COMBINED_PNG" "$OVERLAY_PNG"; do
    if [ ! -s "$output" ]; then
        echo "[$SUBJECT_NAME] FAILED: missing output $output" | tee -a "$LOG_FILE" >&2
        exit 1
    fi
done

echo "[$SUBJECT_NAME] T2-to-T1 registration and QC complete" | tee -a "$LOG_FILE"
