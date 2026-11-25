# Underwater transect model runs

The input manifest supplies source JPEGs, sample times and sequence IDs. Both models receive the same 16 images in the recorded order. Expert boxes, tracks and labels are stored separately. Pixel boxes use left, top, right and bottom coordinates in the source image.

## Box detection and visual descriptions

Use the OceanCV checkpoint at revision `94e22c9ad7da1f504004276cfc8461e21a73b644`. Verify its SHA-256 before loading. The script checks the digest and four ecological groups recorded in the checkpoint. Ultralytics performs letterboxing at image size 1024 with confidence 0.25 and NMS IoU 0.70. Scores are model outputs. [Publisher model card and weights](https://huggingface.co/OceanCV/OOI_Ecotype)

Use the official Qwen3-VL-8B-Instruct Q4_K_M GGUF and F16 visual projector at revision `f982a07559d4a2f6c8744d840bf6fccab30eea96`. Serve this as a separate vision model. The box prompt uses pairs of adjacent frames with known sample times at most five seconds apart and a longest image edge of 1280 pixels. Qwen returns one result per input frame on a 0 to 1000 grid. The script converts coordinates back to original image pixels. Failed or incomplete window responses are retried individually. Outputs identify any frames that failed inference. A qualitative second pass supplies up to eight ordered frames per sequence at a longest edge of 640 pixels. Each hypothesis includes the source frame IDs for review. [Language and vision weights](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF)

```sh
python run_models.py ecotype --manifest inputs/manifest.json --out ecotype.json --weights best.pt --device 0
python run_models.py qwen --manifest inputs/manifest.json --out qwen.json --key-file .vision-key
python describe_sequences.py --manifest inputs/manifest.json --out sequences.json --key-file .vision-key
```

The two box outputs contain model sightings and adjacent-frame track candidates. Each frame can match a previous box of the same model label once, with box intersection over union of at least 0.30. Frame sampling, motion and occlusion can cause splits or mistaken associations. Clip-level answers and box detections require independent review.

## Supplemental seeded mask propagation

The fixed supplemental protocol uses the external benthic sequence and all Ecotype boxes above the existing detection threshold in its first sampled frame. SAM 2.1 Hiera Small receives each box once and propagates its mask through the eight time-ordered samples. It receives no expert boxes, later detector boxes, or expert identities. Positive-logit foreground pixels define the mask, tight display box and mask area. For assessment, associate each starting detector box one-to-one with the first-frame expert boxes using class-agnostic IoU of at least 0.50. For each associated identity, compare the number of later expert-observed frames that retain a matching box at IoU 0.50 under both the original detector track and the SAM track. Also report class-agnostic overlap with a different identity and continuous matched runs. Exclude unsampled animals from any claim about all-frame tracking performance. [SAM 2.1 checkpoint](https://huggingface.co/facebook/sam2.1-hiera-small)

For the seeded run, install the official Meta SAM 2 implementation at revision `2b90b9f5ceec907a1c18123530e92e794ad901a4`. The supplemental run used PyTorch 2.8.0 on CPU and the pinned Hiera Small checkpoint `6d1aa6f30de5c92224f8172114de081d104bbd23dd9dc5c58996f0cad5dc4d38`. The input video consists of the sampled source frames, approximately a second apart. The first-frame seed geometry comes from an independent blind Ecotype pass using Ultralytics 8.3.235 on CPU.

```sh
python track_sam.py --manifest inputs/manifest.json --detector ecotype-reference.json --sequence mbari-bs --weights sam2.1_hiera_small.pt --out sam2.json --device cpu
python score_tracks.py --reference reviewed-manifest.json --detector ecotype-reference.json --sam sam2.json --out sam2-score.json
```

## Structured visual detection retry

The technical retry retains the same image inputs, ecological groups and box task. The server grammar requires one positional property per supplied frame, such as `frame_0` and `frame_1`. Each property contains an array of class and four integer box coordinates. The original run and its failure statuses remain available. This retry records request groups, template, object and token limits and all outcomes in its own output. It retries failures one image at a time. A frame at the token or object ceiling is excluded from complete-frame metrics.

```sh
python qwen_schema_retry.py --manifest inputs/manifest.json --out qwen-schema-retry.json --key-file .vision-key
```
