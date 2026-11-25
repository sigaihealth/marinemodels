# Qwen3-32B on OOI

Open `qwen_chat.ipynb` in JupyterLab, choose the **SIG.AI Ocean (GPU)** kernel, and select **Run → Run All Cells**. Click **Start GPU** if the model is offline. When the status says **Ready**, type a question and click **Send**. Use **New chat** to clear the conversation or **Stop GPU** to release the model memory. After the OOI server restarts, reopen the notebook and start the model again.

The workspace uses a single NVIDIA L40S, an 8,192-token context and one active slot. The model endpoint listens on the workspace loopback interface at port 18732. Both the notebook and the service read an owner-only key created locally. The notebook sends text and retains follow-up turns in kernel memory. Start or stop the same service from a Jupyter terminal with `bash start.sh` or `bash stop.sh` in this directory. If startup fails, see `server.log`.

## Runtime and model

For a fresh installation, run `bash install.sh` in the deployment directory to download the pinned model and runtime. The launcher expects Linux x86-64, Python 3.9 or newer, NVIDIA CUDA driver support, a sibling `runtime/llama-server` executable with its shared libraries in `runtime/`, and the Q4_K_M weights beside the notebook. The notebook kernel also needs ipywidgets.

- [Official Qwen3-32B Q4_K_M GGUF](https://huggingface.co/Qwen/Qwen3-32B-GGUF/blob/938a7432affaec9157f883a87164e2646ae17555/Qwen3-32B-Q4_K_M.gguf), SHA-256 `efd971561896866f0e910cce52761ca77b1b138090c7f15fe284676d57d1f689`.
- [Official llama.cpp b12728 release](https://github.com/ggml-org/llama.cpp/releases/tag/b12728), using `llama-b12728-bin-ubuntu-cuda-12.8-x64.tar.gz` and `cudart-llama-b12728-bin-ubuntu-cuda-12.8-x64.tar.gz`.
