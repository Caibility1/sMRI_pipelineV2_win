#!/bin/bash


template_dir="$2"
# '\UNC-BCP-4D-Infant-Brain-Volumetric-Atlas-Ver2\BCP-atlas-for_release-Ver2.0.0'

subject_dir="$1"

# if [[ -e $subject_dir/T1_acpc.nii.gz ]]; then
#      exit
# fi

echo "The orientation of T1 data"
fslorient $subject_dir/T1.nii.gz


tmp_dir="$1"/"tmp"
if [ ! -e $tmp_dir ]; 
then
   echo "mkdir $tmp_dir"
   mkdir $tmp_dir
fi

IFS='/' read -r -a splits <<< "$subject_dir"
length=${#splits[@]}
sub_name=${splits[$length-1]}

common="-nthreads 20 -quiet -force"

echo "step 1 AC-PC " $sub_name " Alignment ..."

T1_voxel_size=`fslinfo $subject_dir/T1.nii.gz | grep '^pixdim1' | grep -oE '[^[:space:]]+$'`

echo ${T1_voxel_size}

month_str=$(echo $subject_dir | grep -o '[0-9]\+mo' | grep -o '[0-9]\+')
echo "Subject age: ${month_str} months"

# 选择合适的模板月份
if [ $month_str -le 12 ]; then
    # 0-12月使用精确月份，需要补零
    template_month=$(printf "%02d" $month_str)
else
    # 大于12月的情况，选择最近的模板
    available_months=(15 18 21 24 36 48 60)
    template_month="12" # 默认值
    min_diff=999
    
    for m in "${available_months[@]}"; do
        diff=$(( ${month_str#0} - m ))
        diff=${diff#-} # 取绝对值
        if [ $diff -lt $min_diff ]; then
            min_diff=$diff
            template_month=$m
        fi
    done
fi

template_dir="$2/${template_month}Month"
template=`echo BCP-${template_month}M-T1.nii.gz`
echo "T1 with the voxel size -${T1_voxel_size}-, using the template $template from ${template_month}Month."


fslreorient2std $subject_dir/T1.nii.gz $tmp_dir/T1_mni.nii.gz

T1=T1_mni

N4BiasFieldCorrection -d 3 -i $tmp_dir/T1_mni.nii.gz -o $tmp_dir/n8.nii.gz -s 8 -b [200] -c [50x50x50x50,0.000001]
N4BiasFieldCorrection -d 3 -i $tmp_dir/n8.nii.gz -o $tmp_dir/n4.nii.gz -s 4 -b [200] -c [50x50x50x50,0.000001]
N4BiasFieldCorrection -d 3 -i $tmp_dir/n4.nii.gz -o $tmp_dir/T1_mni_n4.nii.gz -s 2 -b [200] -c [50x50x50x50,0.000001]

T1=T1_mni_n4

robustfov -i $tmp_dir/${T1}.nii.gz -m $tmp_dir/roi2full.mat -r $tmp_dir/input_robustfov.nii.gz
convert_xfm -omat $tmp_dir/full2roi.mat -inverse $tmp_dir/roi2full.mat
flirt -interp spline -in $tmp_dir/input_robustfov.nii.gz -ref $template_dir/$template -omat $tmp_dir/roi2std.mat -out $tmp_dir/acpc_mni.nii.gz -cost mutualinfo
convert_xfm -omat $tmp_dir/full2std.mat -concat $tmp_dir/roi2std.mat $tmp_dir/full2roi.mat
aff2rigid $tmp_dir/full2std.mat $tmp_dir/outputmatrix
applywarp --rel --interp=spline -i $tmp_dir/${T1}.nii -r $template_dir/$template --premat=$tmp_dir/outputmatrix -o $subject_dir/T1_acpc.nii.gz

# echo "Aligning DK structure to template space..."
# applywarp --rel --interp=nn -i $subject_dir/dk-struct.nii.gz \
#             -r $template_dir/$template \
#             --premat=$tmp_dir/outputmatrix \
#             -o $subject_dir/dk-struct_acpc.nii.gz

# echo "Aligning tissue segmentation to template space..."
# applywarp --rel --interp=nn -i $subject_dir/tissue.nii.gz \
#             -r $template_dir/$template \
#             --premat=$tmp_dir/outputmatrix \
#             -o $subject_dir/tissue_acpc.nii.gz


rm -r $tmp_dir

# processing T2 file
if [ ! -e $subject_dir/T2.nii.gz ]; 
then
   echo  $sub_name "has no T2 file ..."
   exit
fi

tmp_dir="$1"/"tmp_t2"
if [ ! -e $tmp_dir ]; 
then
   echo "mkdir $tmp_dir"
   mkdir $tmp_dir
fi

template=`echo BCP-${template_month}M-T2.nii.gz`

fslreorient2std $subject_dir/T2.nii.gz $tmp_dir/T2_mni.nii.gz

T2=T2_mni
robustfov -i $tmp_dir/${T2}.nii.gz -m $tmp_dir/roi2full.mat -r $tmp_dir/input_robustfov.nii.gz
convert_xfm -omat $tmp_dir/full2roi.mat -inverse $tmp_dir/roi2full.mat
flirt -interp spline -in $tmp_dir/input_robustfov.nii.gz -ref $template_dir/$template -omat $tmp_dir/roi2std.mat -out $tmp_dir/acpc_mni.nii.gz -cost mutualinfo
convert_xfm -omat $tmp_dir/full2std.mat -concat $tmp_dir/roi2std.mat $tmp_dir/full2roi.mat
aff2rigid $tmp_dir/full2std.mat $tmp_dir/outputmatrix
applywarp --rel --interp=spline -i $tmp_dir/${T2}.nii -r $template_dir/$template --premat=$tmp_dir/outputmatrix -o $tmp_dir/T2_acpc.nii.gz

# registration between T1w and T2w image
#定死dof=6
flirt -in $tmp_dir/T2_acpc.nii.gz -ref $subject_dir/T1_acpc.nii.gz -out $subject_dir/T2_acpc.nii.gz -omat $tmp_dir/T2wToT1w.omat -dof 6

rm -r $tmp_dir

# 计算髓鞘化图（Myelin Map）
echo "Computing myelin map (T1w/T2w ratio)..."

# 创建输出目录（如果不存在）
if [ ! -e $subject_dir/Myelin ]; then
    mkdir $subject_dir/Myelin
fi

# 使用fslmaths计算T1w/T2w比值
fslmaths $subject_dir/T1_acpc.nii.gz -div $subject_dir/T2_acpc.nii.gz $subject_dir/Myelin/T1wDivT2w.nii.gz

# 可选：对myelin map进行平滑处理
sigma=1.5 # 高斯核的标准差（以毫米为单位）
fslmaths $subject_dir/Myelin/T1wDivT2w.nii.gz -s $sigma $subject_dir/Myelin/T1wDivT2w_smooth.nii.gz

