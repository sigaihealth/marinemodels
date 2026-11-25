# How well does a VPR-trained classifier distinguish bubbles from plankton on another cruise?

On the Japanese cruise with expert-labeled examples of both bubbles and organisms, training on Belgian Video Plankton Recorder (VPR) images reduced false bubble calls from 90 of 109 organisms to 5 of 109. The shared classifier recognized all 150 confirmed bubbles. The VPR classifier recognized only 82 (54.7%). Balanced accuracy, which weights bubble and organism recall equally, rose from 58.7% to 75.0%. The VPR model could help experts screen images, but automatically discarding its bubble calls would still remove many real amphipods.

## What changed on each collection?

Each cell gives the **shared model → VPR model** counts over the same expert-labeled images. For bubbles, a higher count is better. For organisms, each count is a false bubble call, so lower is better. A dash means that the panel contained no labeled examples for that column.

| Survey or reference collection | Bubbles recognized | Amphipods called bubbles | Larvae called bubbles | Other organisms called bubbles |
| --- | ---: | ---: | ---: | ---: |
| Japan, *Mirai* MR17-07C | 150/150 → 82/150 | 7/7 → 0/7 | 1/2 → 0/2 | 82/100 → 5/100 |
| Canada, DFO COR2019002 | — | 55/125 → 18/125 | 77/125 → 24/125 | — |
| German Bight, *Heincke* HE446 | — | — | 169/172 → 45/172 | 78/80 → 30/80 |
| German Bight, *Heincke* HE466 | — | — | 181/185 → 6/185 | 72/80 → 15/80 |
| German Bight, *Heincke* HE534 | — | — | 171/176 → 2/176 | 74/76 → 8/76 |
| Hamburg multi-cruise reference library | — | 274/288 → 233/288 | — | — |

Across the deliberately enriched external panel, the fraction of organisms called bubbles fell from 1,241/1,416 (87.6%) to 386/1,416 (27.3%). The reduction was larger for larvae, from 599/660 (90.8%) to 77/660 (11.7%), than for amphipods, from 336/420 (80.0%) to 251/420 (59.8%).

Across the three *Heincke* field cruises, the VPR classifier mislabeled 53 of 533 larvae as bubbles (9.9%), down from 521 (97.7%). Results varied by cruise, ranging from 2 of 176 to 45 of 172. In the Hamburg reference library it continued to flag 233 of 288 amphipods (80.9%). Japan’s seven amphipods and two larvae were correctly kept out of the bubble category, but the exploratory four-group classifier assigned none of the nine to the correct organism group. Across all external collections, the exploratory classifier correctly named 97 of 420 amphipods (23.1%) and 396 of 660 larvae (60.0%). The shared bubble classifier provides only a binary decision.

On the 400-image check from the Belgian training library, false bubble calls fell from 191 to 2 among 200 organisms, while recognized bubbles fell from 199 to 189 among 200. The much steeper drop in bubble recall on the Japanese tow illustrates the importance of testing bubble recall across cruises.

## Training and test collections

We trained the VPR-specific classifier on an NVIDIA L40S at the Ocean Observatories Initiative JupyterHub. Both classifiers used the same frozen image encoder from the SIG.AI 101-class plankton model. The earlier shared bubble classifier had learned from ZooScan and Imaging FlowCytobot images. [Earlier cross-instrument experiment](plankton_bubble_transfer.md)

The VPR fitting set came from the Flanders Marine Institute’s expert-validated Belgian North Sea VPR library. Its 2,500 selected images included 1,250 bubbles, all 68 available amphipods, all 127 named larvae and 1,055 other organisms. The 195 amphipods and larvae had appeared in earlier diagnostic studies and were assigned to training for this experiment. An additional 400 Belgian crops supplied a within-library check. The public Belgian archive lacks an object-to-tow lookup, so images from that check may share an acquisition with training images. [VLIZ training release](https://doi.org/10.14284/607)

The external panel contained 1,566 expert-annotated images. Both classifiers scored all 1,566 crops with thresholds fixed before evaluation. The initial image reader rejected all 250 Canadian 16-bit RGB files. A deterministic conversion to 8-bit RGB recovered these crops for both models. All 1,316 previously accepted cases retained their original decisions. Exact source records, original file hashes and decoded pixel hashes were checked against the training, diagnostic and previous benchmark panels. Multiple frames from a tow can still show the same animal. The selected taxon counts emphasize known errors and cannot estimate their frequency in unsorted survey data.

- **Japan.** The R/V *Mirai* sampled the Okinawa region on October 26, 2017 during JAMSTEC cruise MR17-07C. This deployment supplied all 150 external bubble positives. Its nine targeted animals comprised seven amphipods, one gastropod larva and one krill furcilia. [JAMSTEC cruise report](https://doi.org/10.17596/0002740) · [EcoTaxa annotation project](https://ecotaxa.obs-vlfr.fr/api/projects/3084)
- **Canada.** Fisheries and Oceans Canada’s COR2019002 mission in the southern Gulf of St. Lawrence supplied 125 amphipods and 125 larvae, including 67 fish larvae and 58 crustacean larvae. The sampled projects contained no validated bubble class. Both the Canadian and Japanese panels used EcoTaxa’s human-validated annotations. [DFO processing methods](https://github.com/EOGrady21/vprr/blob/master/vignettes/VPR_processing.Rmd) · [Example Canadian annotation project](https://ecotaxa.obs-vlfr.fr/api/projects/5892)
- **Germany.** University of Hamburg investigators individually checked the field classifications from R/V *Heincke* cruises HE446, HE466 and HE534. The three field panels supplied larvae and controls. All 288 Hamburg amphipods came from the authors’ hand-sorted multi-cruise reference library, which includes material from HE446. Its individual amphipods cannot be assigned to that specific cruise. The Hamburg release has no bubble class. [Plonus and colleagues’ methods](https://doi.org/10.1002/lom3.10413) · [Hamburg image release](https://doi.org/10.5281/zenodo.4431509)

## What to test next

A follow-up study added Japanese and Canadian training data, set aside a subset of the Hamburg reference amphipods, and tested the retrained classifier on two untouched Arctic and Canadian cruises. [Bubble recovery and larval retention on untouched cruises](vpr_bubble_recovery.md)

A useful next evaluation would reserve a new cruise with expert-labeled bubbles, amphipods and larvae from several separate tows. More bubble appearances and difficult amphipods from other cruises could be added to training, while the reserved cruise would measure whether this recovers bubble recall and preserves the gains on larvae. The optical-bubble label in these collections cannot establish performance on surface waves or on native PlankScope imagery.
