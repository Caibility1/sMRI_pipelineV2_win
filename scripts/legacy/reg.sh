#!/bin/bash

# Script to align T2 images to T1 images using rigid body transformation with FSL
# This script will process all subjects in group1-15 folders 
# that HAVE month-age subfolders (*mo suffix)
# It will also generate slice views to check registration quality

# === 从外部获取路径参数 ===
BASE_DIR=$1
QC_IMAGE_DIR=$2

# 检查参数
if [ -z "$BASE_DIR" ] || [ -z "$QC_IMAGE_DIR" ]; then
    echo "Usage: bash reg.sh <BASE_DIR> <QC_IMAGE_DIR>"
    exit 1
fi

mkdir -p "$QC_IMAGE_DIR"

# Output log file
LOG_FILE="registration_log.txt"
echo "FSL T2 to T1 Registration Log" > $LOG_FILE
echo "Started at $(date)" >> $LOG_FILE
echo "----------------------------------------" >> $LOG_FILE

# Check if FSL is available
if [ ! -f "${FSLDIR}/bin/flirt" ] || [ ! -f "${FSLDIR}/bin/slicer" ]; then
    echo "Error: FSL tools (flirt or slicer) not found. Please make sure FSL is installed and FSLDIR is set correctly." | tee -a $LOG_FILE
    exit 1
fi

# For each group folder
# Find all subject directories with "mo" suffix directly under BASE_DIR
for subject_dir in ${BASE_DIR}/*/; do
    if [ ! -d "$subject_dir" ] ; then
        # Skip if not a directory or if the wildcard didn't match
        continue
    fi

    # Get subject name for output files
    SUBJECT_NAME=$(basename "$subject_dir")
    echo "Processing subject: $SUBJECT_NAME" | tee -a $LOG_FILE

    # Look for T1 and T2 files
    T1_FILE=$(find "$subject_dir" -name "T1.nii.gz" -type f)
    T2_FILE=$(find "$subject_dir" -name "T2.nii.gz" -type f)
        
        # Check if both files exist
        if [ -z "$T1_FILE" ] || [ -z "$T2_FILE" ]; then
            echo "    Missing T1 or T2 file, skipping subject" >> $LOG_FILE
            continue
        fi
        
        # Create output directory if it doesn't exist
        OUTPUT_DIR="$subject_dir/registration"
        mkdir -p "$OUTPUT_DIR"
        
        # Output registered file path
        T2_REGISTERED="$OUTPUT_DIR/T2_to_T1.nii.gz"
        TRANSFORM_MATRIX="$OUTPUT_DIR/T2_to_T1.mat"
        
        echo "    Registering T2 to T1 using rigid body transformation (6 DOF)" | tee -a $LOG_FILE
        echo "    T1: $T1_FILE" >> $LOG_FILE
        echo "    T2: $T2_FILE" >> $LOG_FILE
        echo "    Output: $T2_REGISTERED" >> $LOG_FILE
        
        # Run FLIRT with rigid body transformation (6 DOF) using mutual information cost function
        flirt -in "$T2_FILE" \
              -ref "$T1_FILE" \
              -out "$T2_REGISTERED" \
              -omat "$TRANSFORM_MATRIX" \
              -dof 6 \
              -cost mutualinfo \
              -searchrx -90 90 \
              -searchry -90 90 \
              -searchrz -90 90
        
        # Check if registration was successful
        if [ $? -eq 0 ] && [ -f "$T2_REGISTERED" ]; then
            echo "    Registration successful" | tee -a $LOG_FILE
            
            # Create QC images using slicer
            echo "    Generating quality check images" | tee -a $LOG_FILE
            
            # Generate 3-plane overlay images for visual checking
            # Axial view
            AXIAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_axial.png"
            slicer "$T1_FILE" "$T2_REGISTERED" -a "$AXIAL_PNG" 1800 
            
            # Sagittal view
            SAGITTAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_sagittal.png"
            slicer "$T1_FILE" "$T2_REGISTERED" -s "$SAGITTAL_PNG" 1800
            
            # Coronal view
            CORONAL_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_coronal.png"
            slicer "$T1_FILE" "$T2_REGISTERED" -c "$CORONAL_PNG" 1800
            
            # Create a combined multi-view image
            COMBINED_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_combined.png"
            pngappend "$AXIAL_PNG" + "$SAGITTAL_PNG" + "$CORONAL_PNG" "$COMBINED_PNG"
            
            # Use slicer to create a detailed overlay view
            # This shows the T1 with the T2 overlay in a red-yellow color scale
            OVERLAY_PNG="${QC_IMAGE_DIR}/${SUBJECT_NAME}_overlay.png"
            slicer "$T1_FILE" "$T2_REGISTERED" -L -t -s 3 "$OVERLAY_PNG"
            
            echo "    QC images saved to: $QC_IMAGE_DIR" | tee -a $LOG_FILE
        else
            echo "    Registration failed" | tee -a $LOG_FILE
        fi
        
        echo "----------------------------------------" >> $LOG_FILE
    done
done

echo "Registration process completed at $(date)" | tee -a $LOG_FILE
echo "Quality check images are available at: $QC_IMAGE_DIR" | tee -a $LOG_FILE
echo "Check $LOG_FILE for details"

# Print a summary of processed subjects
echo ""
echo "Registration Summary:"
echo "====================="
echo "Number of subjects processed: $(ls -l $QC_IMAGE_DIR/*_combined.png 2>/dev/null | wc -l)"
echo "Quality check images: $QC_IMAGE_DIR"
echo "Log file: $LOG_FILE"
