# Faint appendages in ZooScan images of Themisto

The **primary retrain** recovered **0/2** known *Themisto*. A subsequently designed **alternative operating point** recovered **2/2** on replay and also mislabeled one previously correct PS126 calanoid. On two fresh non-Fram collections reserved for the alternative, it introduced **0/199 new ostracod errors**. It recognized **100/120** broader Nordic hyperiids and **3/3** investigator-labeled *Themisto* from the Iroise Sea. The two recoveries on PS126 and MSM108 are retrospective.

## Primary tests outside Fram Strait

The frozen primary model kept the previous label of other organism on both named targets and added no ostracod errors in the two reserved geographic panels. It retained one earlier false call among 399 expert ostracods.

The predicted target class is amphipod. Investigator labels supply genus or suborder. Read each cell as the previous inherited-error model followed by the faint-appendage model. 543 of 552 registered crops received predictions. The model input limit excluded Hyperiidea (8), Themisto (1).

| Cruise | Expert *Themisto* recognized | Other expert hyperiids recognized | Ostracods called amphipods | Other controls called amphipods |
| --- | ---: | ---: | ---: | ---: |
| South Atlantic, 2010 | 4 → 4 of 4 | — | 0 → 0 of 200 | 22 → 22 of 60 |
| Canadian Arctic / Baffin Bay, 2013 | — | 17 → 17 of 20 | 1 → 1 of 199 | 17 → 17 of 60 |

The 2013 Canadian Arctic and Baffin Bay labels stop at Hyperiidea, the suborder containing *Themisto*. Those 20 images evaluate recognition as amphipods. Only the 2010 South Atlantic cruise had genus-confirmed *Themisto*, with 4 scored examples from one station. This sample limits the precision of a genus-level estimate outside Fram Strait. The two expeditions used the same vessel. Both were distinct by cruise dates, net samples and region from the training collections. Ostracods and other controls were intentionally sampled by taxon; these counts do not measure natural class frequencies. [Tara Oceans campaign registry](https://doi.org/10.1594/PANGAEA.842191) · [Station registry](https://doi.org/10.1594/PANGAEA.842237) · [EcoTaxa genus reference](https://ecotaxa.obs-vlfr.fr/prj/1040) · [Canadian Arctic ZooScan collection](https://ecotaxa.obs-vlfr.fr/prj/378)

The model could reconsider 55 of 399 prospective ostracods, 0 of 4 confirmed *Themisto*, and 1 of 20 broader hyperiids. The model added 0 true *Themisto* and 0 true broader hyperiid calls here. It introduced 0 new false amphipod calls among 120 other control organisms. Where supplied, the counts tables include paired percentage-point intervals resampling entire physical net samples within each cruise. 23 controls were explicitly labeled larvae, with 6 and 6 recognized specifically as larvae before and after retraining.

**Oversized-image sensitivity check.** A separate run proportionally resized the bodies of all 9 excluded images to at most two megapixels and retained their ZooScan footers. On these resized inputs, earlier → retrained recognition was 1 → 1 of 1 *Themisto* and 8 → 8 of 8 other hyperiids. This check used the same frozen weights. The primary counts above use the original-size images only.

## Review of the two earlier misses

The PS126 animal had a dark, compact, tapered body and broad lateral projections. The MSM108 animal was elongated; its broader end narrowed toward faint terminal projections. Both are investigator-labeled *Themisto* to genus. Their compactness values were 0.753 and 0.534, respectively. The reviewer recognized the two animals from the previous study. Their two visual calls therefore cannot provide independent validation. [Earlier study](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_inherited_ostracods.md)

For comparison, the masked review mixed in six other expert *Themisto*, six ostracods and four other crustaceans. Matching prioritized the same acquisition, physical net sample and crop size. Two comparison crops per target taxon and cruise came from the upper third on a pixel measure of faint material outside the dense body. Of the six comparison *Themisto*, the reviewer called five amphipods and abstained on one. The reviewer called four of six ostracods and abstained on two. Of the other crustaceans, three received the broader crustacean call and one an abstention. The investigator labels were retained on every image.

On ambiguous ostracods, a diffuse oval or a few projecting structures obscured the shell. In clearer cases, an enclosing valve rim separated ostracods from amphipods with jointed projections on the inside of a curled body. A faint edge can also reflect blur or overlapping material; the images alone cannot prove which structure drove the model.

## Training evidence

Two previously used training programs supplied 383 additional expert-validated ZooScan images. These included 208 *Themisto*, 95 ostracods and 80 other animals. The APERO Thalassa BIONESS collection contributed 213 images from 56 new scan acquisitions of previously sampled nets. The southern Tara Microbiomes WP2 material contributed 170 images from 5 previously unused net samples. All images stayed in their original program’s validation group. [APERO Thalassa BIONESS](https://ecotaxa.obs-vlfr.fr/prj/11638) · [Tara Microbiomes WP2](https://ecotaxa.obs-vlfr.fr/prj/20784)

A registered image measure selected 150 expert *Themisto* with relatively faint peripheral structures. It compared grayscale intensity outside a high-contrast body with the remaining image signal. The masked visual review found clearly faint projections on six of 16 contrast-selected examples and four of 16 ordinary comparisons. Across both strata, 10 of 32 had clearly faint projections, 10 mixed visibility, 10 readily traceable limbs and two lacked sufficient detail. Taxonomic labels came from investigator validation. The pixel measure enriched the sample for weak image signal, which may include haze.

On the sealed prospective panels, the overlap audit found zero exact matches against 14,091 registered research specimens. The comparison with 6,166 recorded support images and comparisons within the prospective panels found zero retained near-duplicate flags. The original 101-class training inventory was unavailable, so overlap with that original training collection could not be measured.

OOI trained the candidate on its NVIDIA L40S using 3,090 eligible images. The model uses an original image view, a view with boosted low contrast and a view that downweights the dense core. Model parameters and the operating threshold were selected with entire training groups held out in turn. The trained checkpoint was frozen before the two new cruises were scored. Only a prior amphipod call withdrawn by the inherited-error model could be restored; every other model decision was preserved by construction.

## Replay of earlier cruises

Across PS126 and MSM108, *Themisto* recognition went from 188 to 188 of 239; ostracods called amphipods went from 0 to 0 of 310. Across all 8 previous cruises, 1 *Themisto* were restored and 0 ostracod errors were introduced. The model retained 133 of 133 earlier scanner-added *Themisto* calls that were present coming into this study. The previously reviewed rounded PS131 *Themisto* received the label amphipod. Of the 56 inherited errors from the previous study, 1 are now called amphipod.

| Cruise | Expert *Themisto* recognized | Other expert hyperiids recognized | Ostracods called amphipods | Other controls called amphipods |
| --- | ---: | ---: | ---: | ---: |
| MSM108 | 104 → 104 of 128 | — | 0 → 0 of 154 | 17 → 17 of 80 |
| PS121 | 89 → 89 of 94 | — | 1 → 1 of 159 | 27 → 27 of 80 |
| PS126 | 84 → 84 of 111 | — | 0 → 0 of 156 | 17 → 17 of 79 |
| PS131 | 38 → 38 of 44 | — | 0 → 0 of 159 | 20 → 20 of 80 |
| PS136 | 127 → 127 of 195 | — | 0 → 0 of 37 | 33 → 33 of 158 |
| PS78 | 92 → 92 of 111 | — | 0 → 0 of 18 | 21 → 21 of 97 |
| PS80 | 179 → 179 of 235 | — | 0 → 0 of 70 | 32 → 32 of 241 |
| PS85 | 33 → 34 of 39 | — | 0 → 0 of 5 | 24 → 24 of 50 |

## Adaptive follow-up on two further collections

The primary results and two target images were known when the alternative decision policy was proposed. The visual model, score, input processing and set of changeable specimens stayed fixed. A different cutoff was calculated from the initial training folds alone by taking the first registered grid step above the highest-scoring eligible nonamphipod. The threshold and model were frozen before scoring separate Nordic seas and Iroise Sea collections. These two collections provide new performance evidence for the alternative.

On the eight previously evaluated Arctic cruises, the alternative recovered both named animals. Relative to the frozen primary it also recovered a previously missed *T. abyssorum* on PS136. The benefit came with one new false positive, a PS126 calanoid copepod with an investigator label of Calanoida. All 310 PS126 and MSM108 ostracods retained their previous decisions. No new ostracod error appeared on the other six earlier cruises. Of the 56 historical errors identified on PS121 and PS131, 1 remained after applying the alternative. Across the 543 previously scored non-Fram images, the primary and alternative gave identical decisions. The Canadian panel still had one pre-existing ostracod error among 199, and the South Atlantic panel had zero among 200. Those two tests were already known when the follow-up was designed.

In the training folds, the alternative let zero of 169 eligible nonamphipods clear its cutoff. On a broader set of training-fold controls, 3 of 116 other nonamphipods scored above that cutoff, exceeding the original allowance of one. Zero of 166 broader-screen ostracods cleared it. This distinction explains how the stricter primary threshold stayed high enough to miss both animals.

The 2013 expedition followed the Nordic section of Tara’s Lorient–Tromsø voyage. Images came from June 3–7 at 67.12–72.37° N, south of Fram Strait. The expedition used the same schooner and Polar Circle program as the Canadian cruise but different dates, stations and net samples. Target and control taxa were clustered by station. Investigators identified the Arctic amphipods to suborder Hyperiidea. There were no genus-confirmed *Themisto* on this cruise. A separate September 6–7, 2016 Iroise Sea monitoring survey included three genus-confirmed *Themisto* from three WP2 nets. Its field-day vessel was undocumented. There were no verified ostracod controls in that survey. Across both collections, 382 of 382 registered specimens received predictions. [Tara Oceans campaign registry](https://doi.org/10.1594/PANGAEA.842191) · [Station registry](https://doi.org/10.1594/PANGAEA.842237) · [Iroise Sea survey](https://ipt.gbif.org/resource?r=dasid_6511) · [Iroise Sea methods](https://doi.org/10.5194/essd-17-6583-2025)

| Collection | Outcome | Eligible to change | Earlier model | Frozen primary | Alternative |
| --- | --- | ---: | ---: | ---: | ---: |
| Iroise Sea | Expert Themisto recognized as amphipods | 0 of 3 | 3/3 | 3/3 | 3/3 |
| Nordic seas | Expert Hyperiidea recognized as amphipods | 2 of 120 | 99/120 | 99/120 | 100/120 |
| Nordic seas | Expert ostracods called amphipods | 37 of 199 | 0/199 | 0/199 | 0/199 |
| Nordic seas | Other controls called amphipods | 0 of 60 | 15/60 | 15/60 | 15/60 |

The policy changed 1 prediction across the two confirmation collections. It introduced 0 new ostracod errors, leaving 0 total among 199 expert ostracods. It introduced 0 additional errors among 60 other controls. The policy was eligible to change 2 of 120 broader hyperiids and 0 of 3 confirmed *Themisto*. These counts determine how many positive examples could test recovery. [Paired counts for the adaptive and primary rules](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_faint_adaptive.csv)

The public browser serves the established SIG.AI Plankton Classifier. The new research model, specimen views and upload interface run in the private OOI workspace. [Counts by cruise](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_faint_cruises.csv) · [Counts by investigator taxon](https://github.com/sigaihealth/marinemodels/blob/main/docs/zooscan_faint_taxa.csv)
