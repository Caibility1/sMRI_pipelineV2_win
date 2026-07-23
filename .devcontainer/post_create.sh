#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "${repo_root}/cloud_data" "${repo_root}/.secrets"
chmod +x \
    "${repo_root}/bin/smri_reconstruction.sh" \
    "${repo_root}/bin/smri_3d_print.sh"

failed=0
for tool in python3 dcm2niix recon-all mris_convert; do
    if path=$(command -v "$tool" 2>/dev/null); then
        echo "[OK] ${tool}=${path}"
    else
        echo "[FAIL] ${tool} is missing from the Codespace image" >&2
        failed=1
    fi
done

if [ -s "${repo_root}/.secrets/license.txt" ]; then
    echo "[OK] FreeSurfer license is ready"
else
    echo "[ACTION] Upload license.txt to ${repo_root}/.secrets/license.txt"
fi

echo "Codespace workspace: ${repo_root}"
echo "Student data folder: ${repo_root}/cloud_data"
exit "$failed"
