# Visual transect trial

[Open the frame and track reviewer](https://ocean.sig.ai/visual-transect.html). Pick a clip, click an observation and follow its timestamp or track. Toggle model and reference boxes, inspect the Qwen scene notes, or export a review as JSON. The page contains the recorded outputs and both video excerpts. On OOI, `vision_playground.ipynb` accepts new questions and images against the private GPU service.

## Findings

Eight sampled frames per clip were fixed before comparing predictions with labels. The OceanCV seep sequence includes six frames in the published training split and two from its interleaved validation split. All 15 annotated appearances belong to motile epifauna. MBARI Ventana dive V4289 (July 29, 2020) was held out of this comparison. Its eight frames contain 180 annotated appearances across 26 reference tracks. The crosswalk covers 166 appearances across 24 tracks. Fourteen eggcase appearances are outside the ecological comparison. Upstream pretraining exposure is unknown. [Data and source credits](SOURCES.md)

| Sequence | Method | Appearances localized | Localized with correct ecological group |
| --- | --- | ---: | ---: |
| OOI development | OceanCV Ecotype | 15/15 | 15/15 |
| OOI development | Qwen3-VL-8B-Instruct | 0/15 | 0/15 |
| MBARI V4289 | OceanCV Ecotype | 30/166 | 0/166 |
| MBARI V4289 | Qwen3-VL-8B-Instruct | 7/166 | 0/166 |

Localization uses a one-to-one box match at intersection-over-union of at least 0.50. The class-aware pass additionally requires the same ecological group. The counts describe appearances in eight correlated samples, so one individual can contribute several appearances. Both models ran on OOI's NVIDIA L40S. The original Qwen output format yielded 10 usable frames. A label-blind technical rerun with fixed output slots returned valid results for all 16. Both runs and their statuses are archived. [All metrics](results/metrics.json) · [Qwen original](results/qwen-first-pass.json) · [Qwen structured](results/qwen-schema.json)

On V4289, Ecotype produced 33 boxes and labeled every one as sessile. Qwen produced eight boxes and labeled each demersal. Qwen's separate scene description recognized the central octopus, confirmed by MBARI track 1 in every sampled frame, and suggested anemones near it. Three of the pale neighboring animals match expert-labeled urchins. The reviewer links these statements to the frames. [Reviewed observations](sequence-review.json)

## Counting the same animal twice

Ecotype's class-independent spatial matches reached five of the 24 comparable individuals. All four individuals matched in multiple frames received multiple predicted track IDs. Qwen reached one individual, split across three predicted IDs. A separate CPU test seeded SAM 2.1 with all three first-frame Ecotype detections, each matched to an expert urchin. Across their 21 later appearances, both methods located the animals. SAM preserved the three starting identities on 21/21 appearances. The adjacent-box tracker preserved them on 0/21. This measures identity retention conditional on initial detection. The clip provides neither survey area nor effort for an abundance estimate. [Seed-level scores](results/sam2-score.json)

## Rebuild or repeat the trial

Use Python and Pillow for the reviewer, plus FFmpeg to prepare the clips. Run these commands from this directory. Data preparation verifies the publisher data, source JPEGs and blind/reference frame join. Inference receives only the blind manifest and images.

```sh
python prepare_data.py input --with-clips
python build_review.py --manifest input/reference.json \
  --run results/ecotype.json --run results/qwen-schema.json \
  --sequences results/sequences.json --evaluation sequence-review.json \
  --tracking results/sam2.json --tracking-score results/sam2-score.json \
  --output visual-transect.html
```

On the installed OOI workspace, open `~/data/ocean-platform/visual-transect/vision_playground.ipynb` and run its cells. The text and image models have separate ports. If the Jupyter server has restarted, launch the installed vision service from that directory with `nohup bash start_vision.sh > vision-server.log 2>&1 </dev/null &`. Its authenticated inference endpoint binds to loopback and reads a local key file. The trial used the text model's existing llama.cpp b12728 CUDA runtime, an 8,192-token context, Q4_K_M language weights and an F16 image projector.

The public [Qwen checkpoint](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/tree/f982a07559d4a2f6c8744d840bf6fccab30eea96) and [OceanCV checkpoint](https://huggingface.co/OceanCV/OOI_Ecotype/tree/94e22c9ad7da1f504004276cfc8461e21a73b644) are pinned. The Qwen language weights had SHA-256 `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2`; the image projector had `ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38`. The detector runner checks its weights before loading. [Model versions, prompts and tracking protocol](MODELS.md)

```sh
python run_models.py ecotype --manifest input/manifest.json --weights ecotype.pt --device 0 --out results/ecotype.json
python qwen_schema_retry.py --manifest input/manifest.json --key-file .vision-key --out results/qwen-schema.json
python describe_sequences.py --manifest input/manifest.json --key-file .vision-key --out results/sequences.json
```

The original source credits and license terms apply to the embedded imagery and its adaptations. The MBARI excerpt, overlays and derived masks are shared under CC BY-SA 4.0. [Credits and licenses](SOURCES.md)
