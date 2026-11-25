# When does the plankton classifier mistake organisms for bubbles?

On 243 Baltic ZooScan images, pooled retraining reduced false bubble calls from 180 of 180 organisms to 19 of 180. The retrained classifier still recognized 58 of 63 genuine bubbles. Adjusting for the instrument recovered one more genuine bubble (59 of 63) and mislabeled one more organism (20 of 180). On the Belgian North Sea Video Plankton Recorder (VPR), false bubble calls rose from 172 of 180 organisms to 176 of 180 after retraining, including all 68 amphipods.

## Held-out results

The original comparison counts a bubble call when the classifier ranks its bubble/wave category first. The pooled comparison learned from both training instruments together. The adjusted comparison used a correction for a represented instrument and used the pooled result for VPR, which had no training examples. Each comparison scored the same 573 images. Balanced accuracy gives equal weight to the fraction of bubbles recognized and the fraction of organisms correctly kept out of the bubble category.

| Held-out collection | Comparison | Bubbles recognized | Organisms called bubbles | Balanced accuracy |
| --- | --- | ---: | ---: | ---: |
| Baltic ZooScan | Original | 63/63 | 180/180 | 50.0% |
| Baltic ZooScan | Pooled | 58/63 | 19/180 | 90.8% |
| Baltic ZooScan | Instrument-adjusted | 59/63 | 20/180 | 91.3% |
| Belgian North Sea VPR | Original | 144/150 | 172/180 | 50.2% |
| Belgian North Sea VPR | Pooled | 149/150 | 176/180 | 50.8% |
| Belgian North Sea VPR | Instrument-adjusted | 149/150 | 176/180 | 50.8% |

Among 120 Baltic copepod nauplii, false bubble calls fell from 120 to eight with pooling and ten with instrument adjustment. In the VPR collection, false calls increased from 62 to 68 among 68 amphipods. All three comparisons called all eight VPR barnacle cyprids bubbles. These results measure binary bubble discrimination. Species identification requires a separate evaluation.

## Data and scope

The fitting collections were Bay of Biscay ZooScan and Northern Red Sea Imaging FlowCytobot. A total of 462 images were usable for training and 108 were reserved for development. One additional training crop could not be processed. Training and development were separated by cruise day and station for ZooScan and by day for Imaging FlowCytobot. The source investigators validated or manually assigned the labels. [PELGAS Bay of Biscay ZooScan](https://doi.org/10.17882/94052) · [Northern Red Sea IFCB](https://doi.org/10.5281/zenodo.20716677)

Baltic ZooScan and Belgian VPR were held out in full for this fit. Both collections had appeared in earlier evaluations. All 573 test images were new by source ID, original file hash and decoded pixel hash against 14,025 earlier images. Neither test archive supplies a haul identifier for every crop, so the number of independent sampling events is unknown. Counts were selected for this comparison and cannot estimate field prevalence. [SYKE Baltic ZooScan](https://doi.org/10.23729/fa115087-2698-4aa5-aedd-11e260b9694d) · [VLIZ Belgian North Sea VPR](https://doi.org/10.14284/607)

The public positive examples were labeled bubbles. Wave discrimination and native PlankScope performance remain unmeasured. One native PlankScope scene was reserved for expert review. Establishing a native result requires expert-labeled specimens from separate training and held-out collections.
