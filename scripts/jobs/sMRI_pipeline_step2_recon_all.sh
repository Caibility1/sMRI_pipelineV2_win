#!/bin/bash
#SBATCH -p bme_cpu
#SBATCH -N 1
#SBATCH -n 50
#SBATCH -t 7-00:00:00
#SBATCH -o recon_mask_aseg.out
#SBATCH -e recon_mask_aseg.err

module load tools/parallel/20200122
module load apps/fsl/6.0
module load apps/ants

export FREESURFER_HOME=/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/FS8.1
export FS_LICENSE=/public_bme2/bme-zhanghan/linmo2025/Freesurfer8.1/license.txt
source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

export base_dir=/public_bme2/bme-zhanghan/linmo2025/2026/0507_ASD/8_presurf #目录/地址
export SUBJECTS_DIR=$base_dir

process_subject(){
    subj=$1
    age=$(echo "$subj" | grep -oP '(?<=_)\d+(?=mo$)')
    mask_file="$base_dir/$subj/masked.nii.gz"
    aseg_file="$base_dir/$subj/aseg.nii.gz"

    echo "base_dir=$base_dir"
    echo "Processing subject: $subj"
    echo "mask_file=$mask_file"
    echo "aseg_file=$aseg_file"

    if [ ! -f "$mask_file" ]; then
        echo "? Missing masked file: $mask_file"
        echo "$subj" >> failed_subjects.log
        return 0
    fi
    if [ ! -f "$aseg_file" ]; then
        echo "? Missing aseg file: $aseg_file"
        echo "$subj" >> failed_subjects.log
        return 0
    fi

    echo "Processing $subj, age $age months"

    if [ "$age" -eq 0 ]; then
        infant_recon_all --s "$subj" \
            --masked "$mask_file" \
            --segfile "$aseg_file" \
            --newborn \
            --keep-going
    else
        infant_recon_all --s "$subj" \
            --masked "$mask_file" \
            --segfile "$aseg_file" \
            --age "$age" \
            --keep-going
    fi

    if [ $? -ne 0 ]; then
        echo "??  infant_recon_all failed for $subj, skipping."
        echo "$subj" >> failed_subjects.log
        return 0
    fi
}

export -f process_subject

date
echo "=== Start batch processing masked + aseg ==="
ls $base_dir | parallel --jobs 50 --halt never process_subject {}
date
echo "=== Batch done ==="
