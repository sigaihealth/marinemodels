#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "$0")"
rt="$HOME/data/ocean-platform/qwen3-32b/runtime"
export LD_LIBRARY_PATH="$rt"
test -s Qwen3VL-8B-Instruct-Q4_K_M.gguf && test -s mmproj-Qwen3VL-8B-Instruct-F16.gguf
if ! test -s .vision-key; then python3 -c 'import secrets; print(secrets.token_hex(32))' > .vision-key; fi
exec "$rt/llama-server" -m "$PWD/Qwen3VL-8B-Instruct-Q4_K_M.gguf" --mmproj "$PWD/mmproj-Qwen3VL-8B-Instruct-F16.gguf" --alias Qwen3-VL-8B-Instruct --host 127.0.0.1 --port 18733 --api-key-file "$PWD/.vision-key" --device CUDA0 -ngl 99 -c 8192 -np 1 -t 8
