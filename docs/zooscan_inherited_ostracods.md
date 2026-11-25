# Recognizing inherited ostracod errors on Arctic ZooScan images

On two Arctic cruises held back before fitting, ostracod errors went from **55/310 to 0/310**. The model identified **188/239** investigator-labeled *Themisto* as amphipods, compared with **190/239** before this retrain. On the historical error set it corrected **55/56** inherited ostracod mistakes. It restored the rounded PS131 *Themisto* to **amphipod**. A corrected ostracod receives the broad output “other organism.”

## Prospective result on two cruises

R/V *Polarstern* PS126 (2021) and R/V *Maria S. Merian* MSM108 (2022) sampled the Arctic Fram Strait for the HAUSGARTEN monitoring series. Both expeditions were registered by cruise identity before training and held outside model and cutoff selection. The test team selected individuals by investigator-validated taxon and acquisition. These targeted proportions differ from the proportions in an unfiltered ocean sample. Of 710 registered images, 708 were scored and 2 were rejected during preprocessing. Counts use the scored denominator. One PS126 euphausiid and one MSM108 *T. abyssorum* exceeded the four-megapixel input limit. The supporting table records exclusions by source taxon. [PS126 investigators and dataset](https://doi.org/10.1594/PANGAEA.993018) · [MSM108 investigators and dataset](https://doi.org/10.1594/PANGAEA.993019) · [Fram Strait time series](https://doi.org/10.1594/PANGAEA.992948)

Read each sequence from the original classifier through the first ZooScan model, the previous ostracod correction, and this retrain. Species or genus names come from the investigators. The output class is the broad amphipod group.

| Cruise | Expert *Themisto* recognized | Ostracods called amphipods | Other controls called amphipods |
| --- | ---: | ---: | ---: |
| MSM108 | 97 → 105 → 105 → 104 of 128 | 28 → 76 → 28 → 0 of 154 | 18 → 18 → 18 → 17 of 80 |
| PS126 | 72 → 86 → 85 → 84 of 111 | 27 → 84 → 27 → 0 of 156 | 17 → 21 → 19 → 17 of 79 |

55 of 55 ostracod calls inherited from the original classifier were withdrawn. The first scanner model had added 22 true *Themisto* detections over the original on these cruises. Of the 21 gains still present immediately before this retrain, **21 were preserved**. The new model held **21 of the original 22 additions** after including any recoveries. The model lost 2 detections that the original classifier had already made and restored 0 prospective *Themisto*. Both losses were identified to genus by investigators, one on each cruise. Among the 64 fresh *Themisto* meeting the training protocol’s rounded-shape criterion (short-to-long body-axis ratio at least 0.65), detections changed from 49 to 48. Other control organisms called amphipods decreased from 37 to 34 of 159. No new false amphipod calls were introduced in either control group. The by-cruise counts and paired 95% intervals are available in the companion data. Intervals resampled complete net samples 20,000 times within each cruise. These are descriptive comparisons within the same Arctic monitoring program.

The panels included 82 explicitly labeled krill larvae. The preceding and revised models respectively retained 82 and 82 of them as organisms and correctly identified 51 and 51 as larvae. There were no expert-labeled bubbles on these ZooScan cruises.

## Reviewing the inherited errors alongside rounded amphipods

The original classifier called 29 ostracods on PS121 and 27 on PS131 amphipods. The preceding scanner and ostracod models kept all 56 calls. Investigators labeled 52 Ostracoda and four “Ostracoda X.” Both categories have explicit Ostracoda ancestry. The 56 crops came from 29 net samples. [Original PS121 study](https://doi.org/10.1594/PANGAEA.993017) · [Original PS131 study](https://doi.org/10.1594/PANGAEA.993020) · [Earlier correction](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_ostracod_study.md)

We shuffled the 56 specimens, the previously lost PS131 *Themisto*, 22 other expert-labeled *Themisto* and five other crustaceans into seven masked sheets. Comparison specimens came from the same cruises, preferentially the same acquisition or net sample. Eleven of the 22 additional *Themisto* belonged to the most compact 30% of their cruise by the ratio of short to long body axes. The full-resolution review crops retained the source specimen pixels after scale-footer removal. The AI reviewer in the research chat recorded a call, confidence and a visible cue for all 84 images before opening the expert key. The 56 error crops and the rounded PS131 target stayed outside model fitting and calibration.

| Expert-labeled review group | Called ostracod | Called amphipod | Called another crustacean | Abstained |
| --- | ---: | ---: | ---: | ---: |
| 56 inherited ostracod errors | 47 | 0 | 1 | 8 |
| 22 additional *Themisto* | 0 | 22 | 0 | 0 |
| Five other crustaceans | 0 | 0 | 3 | 2 |

Several ostracods had an enclosed dark center with a pale outer rim or paired valve outlines. Long filaments on some ostracods could resemble limbs. The most ambiguous crops had blurry edges, angular or overlapping structures, or projecting appendages with little visible shell. Visible abdominal segments, tail spines and jointed limbs helped distinguish several coiled *Themisto*. The AI reviewer explicitly recognized the rounded PS131 *Themisto* image from the preceding study while making its masked amphipod call. That familiar case is listed separately from the 22 comparison specimens. These results describe this deliberately enriched image set.

## Retraining and test integrity

Additional expert-labeled ZooScan material came from the APERO *Thalassa* BIONESS collection in the North Atlantic and the southern stations of Tara’s Microbiomes program. The two new collections supplied 811 images across 56 source samples, including 329 ostracods, 362 *Themisto* and 120 controls. Of these, 130 *Themisto* were chosen for a relatively compact shape within their source sampling pools. Individual investigator annotations preserved source taxonomy, sample identity and validation status. The private OOI study also used registered historical training collections. The model learns from image features that measure both internal texture and outer shape. OOI trained the research model on an NVIDIA L40S using 2,707 accepted historical and added images (26 preprocessing exclusions). Six training groups were each omitted in turn to select decision thresholds. Southern Tara stations stayed together across expedition legs. The two decisions allowed a false original amphipod call to be withdrawn or a previously lost scanner-added call to be restored. The checkpoint and thresholds were frozen before the prospective cruises were scored. [APERO source project](https://ecotaxa.obs-vlfr.fr/prj/11638) · [Tara southern stations source project](https://ecotaxa.obs-vlfr.fr/prj/20784)

Each current test record was checked against archived object identifiers, source files, normalized PNGs and decoded images. The final panel had zero exact matches against 12,998 prior and fitting observations. Of 720 initial test images, 10 visually similar candidates were conservatively excluded before evaluation. Screening compared rotated and reflected source thumbnails against 5,073 historical and new training images and against the other prospective images. No remaining pair exceeded the registered similarity cutoff. The private archive retains all checked records and applicable preprocessing rejections.

## Replay of previously studied cruises

All preceding model calls in the replay were reproduced by image identity. Of the 56 inherited errors from the visual review, 28 of 29 PS121 cases and 27 of 27 PS131 cases changed from amphipod to other organism. The remaining PS121 ostracod was also an abstention in the masked review. Feathery appendages projected from a compact dark mass, and the shell boundary was unclear. The rounded genus-only PS131 *Themisto* went from other organism to amphipod to other organism, then to amphipod. It represents a single animal image from a familiar collection. Among the 22 additional expert *Themisto* on the contact sheets, both models identified the same 17/22. Across the six historical cruises, all 109 entering scanner additions survived. The retrain restored 3 true detections and withdrew 3 different true detections, leaving 558/718 correct.

| Cruise | Expert *Themisto* recognized | Ostracods called amphipods | Other controls called amphipods |
| --- | ---: | ---: | ---: |
| PS121 | 88 → 89 → 89 → 89 of 94 | 29 → 76 → 29 → 1 of 159 | 27 → 31 → 30 → 27 of 80 |
| PS131 | 36 → 38 → 37 → 38 of 44 | 27 → 86 → 27 → 0 of 159 | 23 → 25 → 23 → 20 of 80 |
| PS136 | 70 → 138 → 129 → 127 of 195 | 5 → 16 → 5 → 0 of 37 | 35 → 38 → 35 → 33 of 158 |
| PS78 | 85 → 92 → 92 → 92 of 111 | 1 → 5 → 1 → 0 of 18 | 27 → 29 → 28 → 21 of 97 |
| PS80 | 141 → 179 → 178 → 179 of 235 | 2 → 5 → 2 → 0 of 70 | 31 → 32 → 32 → 32 of 241 |
| PS85 | 29 → 34 → 33 → 33 of 39 | 0 → 0 → 0 → 0 of 5 | 23 → 28 → 26 → 24 of 50 |

The public Ocean.SIG.AI page offers the established classifier and the aggregate study results. Original reviewed images, per-case model decisions and fitted research weights remain in the private OOI workspace. [Counts by cruise](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_inherited_cruises.csv) · [Counts by expert taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_inherited_taxa.csv)
