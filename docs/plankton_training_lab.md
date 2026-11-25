# Plankton identification and training lab

The public lab accepts a microscope crop and offers two browser models. The OOI identification notebook adds a supervised MobileNetV3 model and image–text retrieval. Choose models whose training images, label vocabulary and scores fit the scientific question. [Open the plankton lab](https://ocean.sig.ai/plankton-lab.html)

| Model | Where to run it | How to read its scores |
| --- | --- | --- |
| WHOI Northeast Shelf IFCB v2.4 | [Browser](https://ocean.sig.ai/try-plankton.html) or identification notebook | Softmax over 155 model categories, including debris. The browser returns three provisional suggestions. |
| Ten-class morphology baseline | [Browser](https://ocean.sig.ai/try-trained-plankton.html) | Each class is represented by its average standardized training measurements. Smaller distances indicate closer matches in size, brightness and shape. |
| MobileNetV3-Small | Identification or training notebook, or [browser with your personal ONNX export](https://ocean.sig.ai/try-mobilenet.html) | A linear head trained on frozen ImageNet features returns softmax scores across ten WHOI categories. Keep the image and model versions when comparing runs. |
| PlankScope ResNet-50 | Identification notebook in an authorized workspace | Ranks 101 native categories. Choose **Compare WHOI + private PlankScope** to save both models’ results, their separate vocabularies and the shared image checksum in one JSON. |
| PML IFCB CLIP-LoRA | Identification notebook | Ranks 145 categories by cosine similarity. Image mode compares a crop with the mean image embedding for each class. Text mode compares the same crop with embeddings of taxonomic lineages. |

## Open the OOI notebooks

1. For a new OOI environment, sign in and run the workspace setup notebook. It opens the public repository in your own JupyterHub server. [Set up the workspace](https://jupyter.oceanobservatories.org/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fsigaihealth%2Fmarinemodels&branch=main&urlpath=lab%2Ftree%2Fmarinemodels%2Fstart_ocean_workspace.ipynb)
2. To identify a crop, open the identification notebook, select the image and the model, and inspect the ranked suggestions. Keep the original image when switching models. The class lists differ across the models, and softmax scores and cosine similarities use different scales. [Identify plankton](https://jupyter.oceanobservatories.org/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fsigaihealth%2Fmarinemodels&branch=main&urlpath=lab%2Ftree%2Fmarinemodels%2Fidentify_plankton.ipynb)
3. To train or inspect the ten-class MobileNet model, open the training notebook. It reuses the stored checkpoint by default. Choose a new run name for a separate fit. [Training notebook](../plankton_workspace.ipynb)

## Reproduce the ten-class experiment

The expanded pilot preserves each crop’s published split. A deterministic instrument-bin assignment keeps acquisitions disjoint, and the data preparation excludes duplicate ROI identifiers and decoded image content. The manifest records the original shard, source row and image checksum. The selected crops cover ten classes, with 128 training and 25 validation images per class. [Preparation code](../prepare_plankton_training_data.py) · [Source dataset](https://doi.org/10.57967/hf/10839)

From the repository root, use a Python environment with PyTorch, TorchVision, Pillow and PyArrow. The preparation command downloads the pinned WHOI shards. If the verified shards already exist locally, pass the directory containing the parquet files with `--source-dir`. The training command automatically selects available CUDA hardware or a CPU. Choose a new output directory for each run.

```sh
data_root="$HOME/data/ocean-platform"
dataset="$data_root/datasets/whoi-nes-2022/pilot"
model_run="$data_root/models/mobilenet-ifcb-reproduction"
python prepare_plankton_training_data.py --all-shards --output "$dataset"
python plankton_workspace.py train --dataset "$dataset" --output "$model_run"
python plankton_workspace.py predict --checkpoint "$model_run/model.pt" \
  --image site/assets/D20260201T002546_IFCB200_00139.png
```

If the manifest is already prepared, start with the training command. `model.pt` contains the frozen backbone, fitted class head, feature scaling and label order. `metrics.json` records the per-class support, precision, recall, F1 and confusion matrix. `validation_predictions.csv` pairs each held-out suggestion with its source label. The morphology baseline can also be fitted from the same manifest. [MobileNet training code](../plankton_workspace.py) · [Morphology training code](../train_morphology_baseline.py)

## Verify the private PlankScope installation

The private workspace stores the original approved checkpoint and ordered label map in an owner-accessible directory. The notebook verifies their fingerprints before loading the model. The public repository includes the loader and the comparison procedure. With the same 24 original Pioneer PNGs, both the OOI CPU and NVIDIA L40S reproduced all 24 top labels from the native Windows run. This tests agreement across implementations. Expert annotations are needed to measure identification accuracy. [Loader](../private_plankscope_runtime.py) · [Reproduction check](../validate_private_plankscope.py)

## Use the GPU-trained model on your own device

In the identification notebook, choose **download your ONNX model**, then **open the local browser runner**. The launch link carries the export fingerprint. Pick your downloaded file and a crop. ONNX Runtime performs inference in the tab. The setup keeps the trained weights and the export receipt in your signed-in workspace at `~/data/ocean-platform/models/mobilenet-ifcb-pilot/`. [Browser runner](https://ocean.sig.ai/try-mobilenet.html) · [Export code](../export_plankton_mobilenet.py)

To validate a personal export, run `python validate_plankton_export.py --dataset "$dataset" --run "$model_run"` with the prepared dataset and the model run containing the ONNX file, its JSON receipt and the PyTorch predictions. [Validation code](../validate_plankton_export.py)

## Held-out results

The 1,280 training crops came from 989 instrument bins. The 250 validation crops came from 211 other bins. The common manifest SHA-256 is `529d03a9cc930528ea19b4c21893e74d0df57bdb801c7242d606858aa7af76d7`.

| Method | Correct / 250 | Accuracy | Macro-F1 |
| --- | ---: | ---: | ---: |
| Training-majority class | 25 | 10.0% | 0.018 |
| Morphology centroid | 131 | 52.4% | 0.507 |
| Frozen MobileNetV3 with fitted head, OOI NVIDIA L40S | 221 | 88.4% | 0.884 |

The OOI NVIDIA L40S run returned MobileNet macro-F1 0.884458 and accuracy 0.884. An independent CPU run matched these metrics. The exported morphology parameters were byte-identical on both machines. The PML model also ran on an IFCB crop with CUDA.

Macro-F1 averages class F1 scores equally. These figures describe a balanced sample of ten WHOI classes. Applying either model to Pioneer imagery introduces different sample composition and possible unfamiliar particles. Measuring accuracy there requires independent expert labels. The WHOI and PML published models use different vocabularies and have no score in this comparison. [Morphology results](../site/assets/ifcb-morphology.json) · [Pioneer audit design](pioneer_roadmap.md)

## Credits

The labeled IFCB dataset is credited to Heidi M. Sosik, Emily E. Peacock, Sidney Batchelder and Joe Futrelle at Woods Hole Oceanographic Institution and is distributed under CC BY 4.0. The public microscope examples come from the NSF Ocean Observatories Initiative’s Pioneer Mid-Atlantic Bight Central Surface Mooring. [Dataset DOI](https://doi.org/10.57967/hf/10839) · [Dataset license](https://creativecommons.org/licenses/by/4.0/) · [Pioneer platform DOI](https://doi.org/10.58046/OOI-CP10CNSM)

The frozen WHOI model is a Sosik Lab release. The MobileNet encoder uses TorchVision’s ImageNet initialization. The PML method uses the authors’ released adapter and prototype banks. [WHOI model](https://huggingface.co/sosiklab/NES-plankton-IFCB-classifier-2022) · [TorchVision MobileNetV3-Small](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.mobilenet_v3_small.html) · [PML paper](https://arxiv.org/abs/2609.11673) · [PML release](https://huggingface.co/danielaivanova/dino_plankton_classifier/tree/2963115132bf29fef94ef9b3eea8d010884b4741)
