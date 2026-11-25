#!/usr/bin/env bash
# Set up the private research workspace using the OOI image's CUDA-enabled PyTorch.
set -euo pipefail
cd "$(dirname "$0")"
root="${OCEAN_WORKSPACE_ROOT:-$HOME/data/ocean-platform}"
base_python="${OCEAN_PYTHON:-python3}"
env="$root/envs/ocean-models-py$("$base_python" -c 'import sys; print(f"{sys.version_info.major}{sys.version_info.minor}")')"
mkdir -p "$root"/{envs,models,results,notebooks,logs}
exec 9>"$root/envs/.plankton-lab.lock"
flock 9
if [[ ! -x "$env/bin/python" ]]; then
    "$base_python" -m venv --system-site-packages "$env"
fi
py="$env/bin/python"
if ! "$py" -c 'import torch, torchvision' ; then
    echo "Choose an OOI image with PyTorch and torchvision, or set OCEAN_PYTHON to a compatible Python." >&2
    exit 1
fi
"$py" -m pip install --disable-pip-version-check 'onnxruntime==1.32.0' 'onnx>=1.19,<2' 'open-clip-torch==3.3.0' 'safetensors==0.8.0' 'ipywidgets>=8,<9' 'ipykernel>=6,<8' 'pyarrow>=15' 'Pillow>=11,<13'
"$py" -m ipykernel install --user --name sigai-ocean --display-name 'SIG.AI Ocean (GPU)'
"$py" stage_ocean_workspace.py --root "$root"
"$py" pioneer_ifcb_prototypes.py --model-dir "$root/models/pml-ifcb-clip-lora" --prepare
data="$root/datasets/whoi-nes-2022/pilot"
"$py" prepare_plankton_training_data.py --all-shards --source-dir "$root/datasets/whoi-nes-2022/source/data" --output "$data"
run="$root/models/mobilenet-ifcb-pilot"
if [[ -f "$run/model.pt" ]]; then
    "$py" - "$data/manifest.csv" "$run/metrics.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
digest = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
if digest != json.loads(Path(sys.argv[2]).read_text())['manifest_sha256']:
    raise ValueError("Existing model used another dataset. Select a new workspace root.")
print("Reusing the trained checkpoint.")
PY
else
    "$py" plankton_workspace.py train --dataset "$data" --output "$run"
fi
# The personal ONNX export lets the same trained model run on a researcher's device.
receipt=$(mktemp "$run/.onnx-export.XXXXXXXX")
trap 'rm -f "$receipt"' EXIT
"$py" export_plankton_mobilenet.py --checkpoint "$run/model.pt" --output "$run/mobilenet-pilot.onnx" > "$receipt"
mv "$receipt" "$run/onnx-export.json"
"$py" train_morphology_baseline.py --dataset "$data" --output "$root/models/ifcb-morphology.json"
for notebook in identify_plankton.ipynb plankton_workspace.ipynb start_ocean_workspace.ipynb; do
    if [[ ! -e "$root/notebooks/$notebook" ]]; then
        cp "$notebook" "$root/notebooks/$notebook"
    fi
done
mkdir -p "$root/docs"
if [[ -f docs/plankton_training_lab.md ]]; then
    cp docs/plankton_training_lab.md "$root/docs/"
fi
echo "Ready. Open identify_plankton.ipynb and run all cells with the SIG.AI Ocean (GPU) kernel."
