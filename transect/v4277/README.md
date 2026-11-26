# How many animals did two detectors find on Ventana dive V4277?

[Open the V4277 review on ocean.sig.ai](https://ocean.sig.ai/v4277.html). Inspect a full seafloor frame or zoom into a target, toggle the expert and detector boxes, and save or export a review decision. The 18 examples cover joint misses, detector disagreements, joint matches and unmatched proposals. The page also lists all 94 reference tracks.

OOI's NVIDIA L40S ran OceanCV Ecotype and FathomNet Megalodon 2024 YOLO11x on all 600 original JPEGs of MBARI’s Benthic Difficult clip. MBARI filmed this approximately 20-second sequence on February 19, 2020. Both models saw identical images without annotations. Each published reference box and detection could participate in a single match per frame at intersection-over-union of at least 0.50. The question was whether the detector localized an animal. The reference taxon is used to analyze who was missed. [Frozen scoring protocol](PROTOCOL.md) · [Data and credits](SOURCES.md) · [Model versions](MODELS.md)

| Result | OceanCV Ecotype | FathomNet Megalodon |
| --- | ---: | ---: |
| Expert individuals with at least one match | 51/94 | 91/94 |
| Expert appearances localized | 3,472/28,708 (12.1%) | 18,926/28,708 (65.9%) |
| Returned boxes with an expert match | 3,472/4,423 (78.5%) | 18,926/19,528 (96.9%) |
| Median fraction of an individual's annotated frames localized | 0.36% | 67.4% |

Megalodon reached 40 individuals Ecotype never reached. Ecotype supplied three additional appearance matches, all on individuals Megalodon had found elsewhere in the clip. These two complementary counts help a reviewer decide whether it is worth inspecting a second detector’s suggestions. Published tracks supply the individual identities. This experiment measures detection coverage, with no assessment of automated tracking, species identification or human review time. [Per-track results](results/tracks.csv) · [All metrics](results/metrics.json)

## Who was missed?

| Expert taxon | Reference individuals | Ecotype reached | Megalodon reached |
| --- | ---: | ---: | ---: |
| Funiculina_Balticina complex (sea pens) | 81 | 47 | 79 |
| Umbellula | 4 | 2 | 4 |
| Sebastolobus | 4 | 1 | 4 |
| Strongylocentrotus fragilis (urchins) | 5 | 1 | 4 |

Across both detectors, 9,779 annotated appearances had no one-to-one match. Three expert individuals had no unique match at any time. Start with these examples in the viewer.

| Track | Expert label | Annotated frames | Evidence for review |
| --- | --- | ---: | --- |
| 13 | Sea pen | 400 | A Megalodon box overlapped the reference sufficiently on 35 frames. Those boxes were assigned to other reference animals. Inspect neighboring boxes and their relative fit. |
| 511 | Sea pen | 280 | Median reference box about 13 × 11 pixels in the original 1920 × 1080 frame. Neither detector supplied an eligible overlapping box. |
| 502 | Urchin | 279 | Median reference box about 18 × 18 pixels. Neither detector supplied an eligible overlapping box. |

The box-size and overlap checks were performed after scoring. Median box width and height are calculated separately and rounded to the nearest pixel. The overlap check inspects every returned box at the fixed confidence threshold. An object below that threshold could still have received a raw network response. [Miss diagnostics](results/missed-track-details.json) · [Review cases](results/review-cases.json)

Megalodon is the more productive starting detector for this clip. A reviewer can check adjacent animals on track 13 and test whether native-resolution crops make tracks 511 and 502 easier to distinguish. The heavy concentration of one sea-pen complex limits transfer to other habitats. Both midwater dives, V4455 and V4432, remain reserved for the next test. Upstream checkpoint exposure to related MBARI footage is unknown.

## Reproduce

From this directory, prepare the imagery and the expert reference. The standard-library script verifies the pinned files and frame timestamps. The scorer needs SciPy, NumPy and Pillow. The recorded evaluation used SciPy 1.18.1 and NumPy 2.5.5. The archive includes the unaltered OOI outputs, settings, weight hashes, GPU runtime records and blind input manifest. [Download both GPU prediction files](results/predictions.zip)

```sh
python prepare_data.py data --stage all
python -m zipfile -e results/predictions.zip results/raw
python score.py --reference data/reference.json --manifest data/blind/manifest.json \
  --ecotype results/raw/ecotype.json --megalodon results/raw/megalodon.json \
  --miss-details results/missed-track-details.json --output rebuilt
python inspect_misses.py --reference data/reference.json --tracks rebuilt/tracks.csv \
  --ecotype results/raw/ecotype.json --megalodon results/raw/megalodon.json \
  --out rebuilt/missed-track-details.json
```

For a new model run use the CUDA commands in [MODELS.md](MODELS.md). The registered run used batch size four, image size 1024, confidence 0.25 and classwise suppression at IoU 0.70. All frames completed without hitting the 300-box cap. The scoring IoU is separate from the detector suppression threshold. The [appearance audit](results/appearances.csv.gz) and [prediction audit](results/predictions.csv.gz) retain the frame-level matches.

Source imagery and adapted crops are credited to Kevin Barnard, Elaine Liu, Kristine Walz, Brian Schlining, Nancy Jacobsen Stout, Lonny Lundsten and MBARI under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The viewer resizes the images, crops targets and adds overlays. The original video, unaltered JPEGs, labels, run outputs and reviewer are also available in the personal OOI workspace at `~/data/ocean-platform/visual-transect/v4277/`.
