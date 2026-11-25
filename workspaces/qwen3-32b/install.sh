#!/usr/bin/env bash
# Run in the persistent, private OOI chat folder after copying the notebook and scripts.
set -euo pipefail
umask 077
cd -- "$(dirname -- "$0")"
exec 9>.install.lock
flock 9
release=https://github.com/ggml-org/llama.cpp/releases/download/b12728
model=Qwen3-32B-Q4_K_M.gguf
digest=efd971561896866f0e910cce52761ca77b1b138090c7f15fe284676d57d1f689
matches() { printf '%s  %s\n' "$1" "$2" | sha256sum --check --status; }

if [[ ! -x runtime/llama-server ]]; then
    staging=$(mktemp -d .qwen-runtime-XXXXXXXX)
    trap 'rm -rf -- "$staging"' EXIT
    mkdir "$staging/runtime"
    for variant in 'llama-b12728-bin-ubuntu-cuda-12.8-x64.tar.gz' 'cudart-llama-b12728-bin-ubuntu-cuda-12.8-x64.tar.gz'; do
        case "$variant" in
            llama-*) archive_digest=fa933e8c59cecfca0f4eda3358afca026fb1557f857a7e86896820fabef7b0af ;;
            cudart-*) archive_digest=682f4ee2bd14383654ec918b03c33f544db1c3f8490af2171447f18e24b79e73 ;;
        esac
        curl --fail --location --silent --show-error --retry 3 -o "$staging/$variant" "$release/$variant"
        matches "$archive_digest" "$staging/$variant"
        tar --strip-components=1 -xzf "$staging/$variant" -C "$staging/runtime"
    done
    mv -T "$staging/runtime" runtime
fi

if [[ ! -f "$model" ]]; then
    mirror="https://www.modelscope.cn/api/v1/models/Qwen/Qwen3-32B-GGUF/repo?Revision=7bd9b0147e1ea387abb1a27b35f0be79bfef5f99&FilePath=$model"
    primary="https://huggingface.co/Qwen/Qwen3-32B-GGUF/resolve/938a7432affaec9157f883a87164e2646ae17555/$model"
    partial="$model.download"
    curl -fLsS --connect-timeout 15 --retry 2 -C - -o "$partial" "$mirror" ||
        curl -fLsS --connect-timeout 15 --retry 2 -C - -o "$partial" "$primary"
    matches "$digest" "$partial" || { echo "Downloaded file failed SHA-256 verification." >&2; exit 1; }
    mv -- "$partial" "$model"
else
    matches "$digest" "$model" || { echo "Existing model failed SHA-256 verification." >&2; exit 1; }
fi
LD_LIBRARY_PATH="$PWD/runtime${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" runtime/llama-server --list-devices
