# SIG.AI Plankton Classifier

Researchers can choose a sample or submit a single opaque grayscale or RGB PNG crop. SIG.AI processes the original pixels on its server and returns three candidates from 101 categories. Scores rank the categories for that image. An ordinary classification processes the PNG in memory. After classifying their own image, researchers can separately opt in to contribute the crop for training and evaluation. The contribution service stores the re-encoded pixels privately and returns a withdrawal receipt. Contributions expire after 28 days and the daily cleanup removes expired records. [Contribution and withdrawal details](https://ocean.sig.ai/data-and-privacy.html#contributions). [Open the browser trial](https://ocean.sig.ai/sigai-plankton.html)

## Research contributions

Selecting Classify crop never adds an image to the research collection. An explicit, separate contribution sends the PNG for metadata stripping and private storage. A researcher can download a withdrawal receipt and use it on the classifier page to remove the stored crop. A prediction JSON or image checksum is not a withdrawal receipt.

The collection supports future training and evaluation. Before using it, exclude expired and withdrawn contributions. Keep temporary research copies within the same retention period and out of public datasets or issues.

## Optional IFCB reference check

The Imaging FlowCytobot (IFCB) reference check addresses a narrower question. Does the crop resemble a copepod nauplius, *Coscinodiscus*, *Leptocylindrus* or *Phaeocystis* in the WHOI Northeast Shelf collection? Selecting the check adds a separate suggestion or recommends expert review. The main 101-category predictions are available alongside it.

The evaluation used expert-labeled images from Heidi M. Sosik, Emily E. Peacock, Sidney Batchelder and Joe Futrelle at Woods Hole Oceanographic Institution. The team fitted the reference classifier on 500 images from 465 instrument acquisitions, set its review threshold on 130 images from 127 acquisitions, and evaluated the resulting procedure once on 148 images from 142 other acquisitions. All three sets had disjoint acquisition bins. Duplicate ROI identifiers and decoded pixels were excluded. The test used the published validation partition. [WHOI dataset, CC BY 4.0](https://doi.org/10.57967/hf/10839)

| Held-out question | Result |
| --- | --- |
| Given 88 crops known to belong to one of the four groups, which group fits best? | The reference classifier selected the correct group on 87/88. The original classifier, restricted to those same groups using a provisional taxonomic mapping, selected the correct group on 28/88. |
| When 60 crops from outside the four groups were included, when did the system issue an identification? | Across all 148 crops, it issued 82 suggestions. Of these, 77 matched the expert label (93.9%). It flagged the other 66 crops for expert review. |
| How often did it assign an outside crop to one of the four groups? | 4/60. All four came from the 30 examples of groups absent from training and threshold selection. |

The 88 in-scope crops included 22 per group. The baseline comparison pooled related native *Phaeocystis* categories to account for differences in taxonomic granularity. The balanced sample and the four-group scope limit what these numbers establish about other waters, instruments and categories. Biological accuracy across all 101 categories and on Pioneer storm imagery still needs independent expert labels.

As an implementation check, the hosted model reproduced the original Windows classifier's top labels on all 24 byte-matched Pioneer replay crops. The storm samples are supplied without an independent biological identification. [Pioneer case study](https://ocean.sig.ai/pioneer-storm.html)

## Six-collection benchmark

The expanded study tested the 101-way ranking on 3,254 annotated images with reference labels for 28 categories. Two entire collections were held out to measure transfer. [Results by collection and evaluation methods](plankton_benchmark_six_collections.md)
