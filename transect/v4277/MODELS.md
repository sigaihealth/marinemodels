# V4277 detector comparison

Both detectors process the same ordered blind manifest of native source JPEGs. The runner verifies every image and both weight files by SHA-256 before inference. The outputs retain source-pixel bounding boxes, checkpoint labels and confidence scores for later class-independent evaluation.

| Method | Actual checkpoint classes | Publisher / revision | SHA-256 |
| --- | --- | --- | --- |
| OceanCV OOI Ecotype | Demersal, Motile Epifauna, Planktonic, Sessile Epifauna | [OceanCV, 94e22c9](https://huggingface.co/OceanCV/OOI_Ecotype/tree/94e22c9ad7da1f504004276cfc8461e21a73b644), repository marked MIT | `7c521bf59be99c1098b2bbc136011e59bc3fed08af69b99063a4264ca72fc427` |
| FathomNet Megalodon 2024 YOLO11x | item | [FathomNet / MBARI, 403704d](https://huggingface.co/FathomNet/megalodon-2024-yolov11/tree/403704d2d4dba9903ffbdd215648c3fc8ae6f377), CC BY 4.0 | `27ab91d07fa61d6ae1af9a2c18e29d6b89044254aec7d38b1a4331cbb9b3a450` |

MBARI calls the Megalodon class “object” on its [model card](https://huggingface.co/FathomNet/megalodon-2024-yolov11/blob/403704d2d4dba9903ffbdd215648c3fc8ae6f377/README.md). The weights serialize the class name as `item`. Its proposals can cover poorly characterized objects. Researchers should validate whether an unmatched proposal shows an organism. The checkpoint license and inference software license apply separately.

The settings were fixed before running on V4277. Both models use rectangular letterboxing at a maximum edge of 1,024 pixels, confidence threshold 0.25, standard classwise NMS at IoU 0.70, at most 300 detections per frame, full-precision inference and no augmentation. NMS runs independently within each Ecotype label. For the single-class Megalodon model all proposals use one label. The output records frames reaching the cap. Inference runs sequentially by model, in batches of four images on CUDA. The prespecified memory fallback is to rerun both methods at batch size one if required. Both result files identify their batch size, runtime, GPU, peak allocated Torch memory and elapsed inference time. The output includes one frame record for each input, including successful frames with zero detections. A failed run does not publish a partial result.

The earlier pilot established the settings on V4289. V4277 is held out of the present workflow. The pretrained checkpoints' exposure to V4277 or related MBARI footage remains uncertain. MBARI's own benchmark evaluated an earlier YOLOv8x Megalodon with a tracker. This run uses the separately published 2024 YOLO11x still-image detector. [DeepSea-MOT methods and benchmark](https://arxiv.org/html/2509.03499v1)

## Run on OOI

Use Python 3.11+ with compatible CUDA PyTorch, torchvision and Ultralytics. Directory names below assume the installed V4277 trial and the parent visual-transect workspace. The `--fetch` option downloads an absent file from its pinned publisher repository.

```sh
python run_detectors.py ecotype --manifest blind/manifest.json \
  --weights ../ecotype.pt --device 0 --out results/ecotype.json
python run_detectors.py megalodon --manifest blind/manifest.json \
  --weights weights/megalodon.pt --fetch --device 0 --out results/megalodon.json
```
