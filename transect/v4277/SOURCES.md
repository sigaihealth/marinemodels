# Ventana V4277 source and reference

DeepSea MOT’s full Benthic Difficult sequence contains 600 expert-reviewed frames from Monterey Bay Aquarium Research Institute’s ROV Ventana. The original filename identifies dive V4277 and the recording dated February 19, 2020, with the marker 21:12:38 UTC. The offset of this excerpt within that recording is unknown. The original and current first-frame XML records contain identical objects and boxes. The earlier V4289 clip is from a different dive. [Original dive filename](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT/blob/2163f4bdd04143222f1eebfe618904f765f6c934/data/BD/xml/BD_001.xml) · [Pinned source files](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT/tree/61ecbda8acb2749f3771d7192c51341267da2f37/data/BD)

The 600 original JPEGs total 195,033,608 bytes. Each is 1920 × 1080. The original MOV is 27,580,878 bytes, with nominal rate 30000/1001 frames per second, 600 frames and a 20.015767-second video stream. Frame numbers start at 1. Timestamps are relative to the clip. The actual presentation timestamp in 1/30000-second ticks is zero for frame 1 and `(frame_index - 1) × 1001 - 127` thereafter. The last frame starts at 19.9824 seconds. All 600 timestamps were checked with FFprobe. Spot comparisons between source JPEGs and matching MOV frames used grayscale Pearson correlation after resizing to 144 × 81. Correlations at frames 1, 201, 400 and 600 were 0.99921, 0.99767, 0.99763 and 0.99772.

The authors describe starting with detections and automatically proposed tracks, then manually editing boxes and adding overlooked animals across all frames. This trial uses the published reference. Initial annotator proposals may affect which hard animals entered the reference. Training exposure for existing detector weights is unknown. This sequence is a single, sea-pen-dominated benthic dive. [DeepSea MOT benchmark methods](https://arxiv.org/html/2509.03499v1)

| Publisher taxon | Expert tracks | Annotated frame appearances |
| --- | ---: | ---: |
| Funiculina_Balticina complex | 81 | 25,499 |
| Strongylocentrotus fragilis | 5 | 1,416 |
| Sebastolobus | 4 | 1,097 |
| Umbellula | 4 | 696 |
| **Total** | **94** | **28,708** |

The taxon attached to each track is consistent over its labeled lifetime. Published names are retained verbatim. Each track and frame combination occurs once. XML and the publisher's MOT table agree on all 28,708 frame and track ID pairs. Their box coordinates differ by at most 1.005344 source pixels because the published representations use different precision. Scoring uses XML box corners in source pixels, with 38 annotations clipped to image boundaries by at most 0.000977 pixels. These records also retain the original coordinates under `source_bbox`.

## Reproduce

```sh
python prepare_data.py data --stage blind --workers 12
python prepare_data.py data --stage reference --workers 12
python prepare_data.py data --stage video
python prepare_data.py data --stage all --offline
```

Python's standard library is sufficient. Downloads are pinned to the revisions in the links above. The blind stage fetches only V4277 images and their public inventory. The reference stage fetches only V4277 XML, its MOT table and provenance record. Published image SHA-256 and XML Git blob IDs are verified against pinned directory inventories. The script writes the inference inputs to `data/blind/` and the separate annotated `data/reference.json`. Expected SHA-256 digests are in [data_audit.json](data_audit.json). Images, original labels and video can be kept in the researcher’s data workspace.

## Attribution and reuse

Kevin Barnard, Elaine Liu, Kristine Walz, Brian Schlining, Nancy Jacobsen Stout and Lonny Lundsten, Monterey Bay Aquarium Research Institute, *DeepSea MOT: A benchmark dataset for multi-object tracking on deep-sea video* (2025). The publisher licenses DeepSea MOT under CC BY-SA 4.0. Attribute MBARI and the authors, identify changes to excerpts or overlays, and share adaptations of their material under the same license. The JSON representation preserves the taxon and track IDs and clips the subpixel edge coordinates described above. [Dataset card](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
