# Can the VPR classifier recover missed bubbles and keep larvae?

On an Arctic cruise held out from training and model selection, the retrained SIG.AI Video Plankton Recorder (VPR) classifier recognized **146 of 220 optical bubbles (66.4%)**, up from **130 (59.1%)**. The gain varied considerably by acquisition. On a separate Canadian cruise, it kept **241 of 250 expert-labeled larvae (96.4%)** out of the bubble category, up from **64 (25.6%)**. The Arctic cruise supplied the bubble evidence and the Canadian cruise supplied the larval evidence. [Earlier VPR experiment](vpr_bubble_transfer.md)

## Results on the two untouched cruises

All three classifiers scored the same 584 images. For an organism, “retained” means the model classified the image as something other than a bubble. Higher counts are better in every row.

| Cruise and outcome | Shared classifier | Prior VPR classifier | Retrained VPR classifier |
| --- | ---: | ---: | ---: |
| Arctic HLY1601, bubbles recognized | 199/220 | 130/220 | 146/220 |
| Arctic HLY1601, amphipods retained | 0/14 | 13/14 | 14/14 |
| Arctic HLY1601, other named organisms retained | 7/100 | 95/100 | 90/100 |
| Canada CAR2022299, larvae retained | 17/250 | 64/250 | 241/250 |

The Arctic panel came from the USCGC *Healy* expedition to the Chukchi Borderlands in 2016. The retrained classifier recognized 54 bubbles the prior VPR model missed and missed 38 the prior model recognized. Six of nine acquisitions improved, two declined and one tied. The observed gain was **7.3 percentage points**, with a 95% paired acquisition-bootstrap interval of **−12.7 to +25.1 points**. Either a loss or a gain in bubble recall is consistent with the variation among acquisitions on this cruise. False bubble calls across the 114 Arctic organisms rose from 6 to 10. [JAMSTEC annotations](https://ecotaxa.obs-vlfr.fr/api/projects/3177) · [NOAA expedition archive](https://www.ncei.noaa.gov/archive/archive-management-system/OAS/bin/prd/jquery/accession/details/190784)

Fisheries and Oceans Canada collected the larval images in the Gulf of St. Lawrence in 2022. The retrained model recovered 177 larvae previously called bubbles and kept every larva the prior model retained. Retention improved in all 46 sampled acquisitions, a gain of **70.8 percentage points** with a 95% paired acquisition-bootstrap interval of **+64.8 to +76.5 points**. Both intervals use 20,000 paired resamples of whole acquisitions within the respective cruise. They describe variation within one expedition for each outcome. [Canadian VPR annotations](https://ecotaxa.obs-vlfr.fr/api/projects/10429) · [DFO instrument workflow](https://cran.r-project.org/web/packages/vprr/vignettes/VPR_processing.html)

## Does the model name the organisms it keeps?

The retrained classifier used the label “larva” for 124/250 Canadian larvae, up from 0/250. It recognized 45/65 fish larvae and 79/128 crab or other decapod zoeae. It gave the larva label to 0/35 molluscan veligers and 0/22 nemertean pilidia. On the Arctic panel, it placed all 14 amphipods in “other organism.” The prior model had specifically recognized 4/14 as amphipods.

The Hamburg reference library showed a different result. We used 193 of its 288 hand-sorted amphipods for training. We reserved all 95 images from one source filename prefix and checked for visually similar images across the split. The prior model called 83/95 reserved amphipods bubbles and named 2/95 as amphipods. The retrained model called **0/95** bubbles and named **95/95** as amphipods. Individual source files lack a reliable cruise identifier. The result shows how well the model learned this particular library and helps explain why the independent Arctic check matters. [University of Hamburg image release](https://doi.org/10.5281/zenodo.4431509) · [Plonus and colleagues’ methods](https://doi.org/10.1002/lom3.10413)

## Bubble recall on two more Japanese deployments

We used the frozen model on two additional *Mirai* deployments from October 24–25, 2017. These deployments came from the same cruise, MR17-07C, as an October 26 operation used in training. On the first deployment, bubble detections rose from 50/80 to 76/80. On the second they rose from 50/80 to 77/80. Together that is **100/160 to 153/160** (62.5% to 95.6%). The model recovered 54 previously missed bubbles and missed one previously detected bubble. False bubble calls on organisms fell from 3/36 to 0/36, although specific recognition of the five amphipods fell from 2/5 to 0/5. These results measure transfer between stations of the same cruise. [First VPR deployment](https://ecotaxa.obs-vlfr.fr/api/projects/3108) · [Second VPR deployment](https://ecotaxa.obs-vlfr.fr/api/projects/3109) · [JAMSTEC cruise report](https://doi.org/10.17596/0002740)

## Training and evaluation design

We trained on 4,092 expert-labeled VPR crops using the Ocean Observatories Initiative’s NVIDIA L40S GPU. The fitting set included the original 2,500 Belgian training crops and 1,592 additional crops. New sources included bubbles and organisms from JAMSTEC’s *Mirai* cruise MR17-03C and echinoderm larvae and other organisms from DFO mission IML2018051. Separate stations from those cruises contributed to the 1,132-image development set. We also reused portions of the previously evaluated Japanese, German and Canadian collections in training and development. One visually near-identical German larval image was removed across partitions. [Belgian VPR release](https://doi.org/10.14284/607) · [MR17-03C annotations](https://ecotaxa.obs-vlfr.fr/api/projects/3181) · [IML2018051 annotations](https://ecotaxa.obs-vlfr.fr/api/projects/5880)

We selected the model and bubble threshold on the development set, then froze both before scoring HLY1601 and CAR2022299. Every project from those two cruises stayed out of fitting and model selection. Original records, source images and decoded pixels were checked for exact overlap. Multiple frames from one acquisition can still depict the same organism. We selected cases by expert category to measure errors on difficult groups. Their frequencies in these panels cannot estimate ocean abundances or the fraction of a whole survey that would be discarded.

A follow-up traced the two declining Healy acquisitions and evaluated a new VPR model on fresh cruises. [Healy error diagnosis and fresh-cruise results](vpr_healy_error_study.md)
