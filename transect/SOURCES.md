# Sources and independent evaluation

The trial uses two eight-second ROV excerpts and eight systematic observations from each. All observations were selected before scoring either model. The blind input package contains JPEGs and sequence metadata. Reference boxes and tracks are stored separately for evaluation.

## Reproduce the data

Run these commands from the repository root with Python 3.9 or newer. Use an output directory outside the checkout. The default fetch is about 64 MB. The optional movies add approximately 1.15 GB of source downloads and require FFmpeg with libx264.

```sh
python3 transect/prepare_data.py /tmp/transect-pilot
python3 transect/prepare_data.py /tmp/transect-pilot --verify-only
python3 transect/prepare_data.py /tmp/transect-pilot --with-clips
```

The first command checks the pinned OceanCV archive, eight MBARI JPEGs and eight MBARI XML files, then reproduces each reference box, ecological assignment and available track ID from the publisher data. The offline verification checks all 16 JPEG hashes and joins the blind manifest one-to-one against the Git reference. The cache can also be reused to regenerate a new directory offline.

```sh
python3 transect/prepare_data.py /tmp/transect-repeat --offline --cache /tmp/transect-pilot/source-cache
```

For inference, supply only the staged `manifest.json` and `images/`. For scoring and review, use the separate `reference.json`, which adds the original taxon, track ID, source split, annotations, crosswalk, licensing and recovered dive provenance. All boxes use the source JPEG's pixels in left, top, right, bottom order. `data_audit.json` records SHA-256 digests of the upstream downloads, the original run's input ZIP, the JPEG overlap check and the frame-to-video correlations. Every image digest and upstream URL is in `reference.json`. The decoded source frame range defines each review clip. Its reencoded bytes can depend on the FFmpeg build.

## OceanCV seep transect

OceanCV's published exercise credits OOI, the University of Washington, NSF and Carter (2025). We used its MIT-licensed video and MIT-licensed EcotypeTransect annotation export. The model card lists this dataset among its training sources. The archive contains 1,776 source JPEGs, split by frame between training and validation. Our first eight exported frames (numbers 0, 32, 64, 96, 128, 160, 192 and 224) are interleaved across those partitions. Six are training frames and two are validation frames. These images demonstrate the workflow. All 15 source boxes in this short window are marked Motile Epifauna. Each source box has an unknown individual ID and reviewer. No reliable original ROV dive number or UTC appears in these records.

The source video has 68,625 frames at exactly 29 frames per second. We joined images to video using the publisher's frame numbers and extraction recipe. Source images are 1024 × 576, while the compressed teaching video is encoded at 1024 × 768. The browser excerpt restores the labeled images' aspect ratio. The correlation between a 64 × 36 grayscale version of each original JPEG and the corresponding decoded video frame exceeded 0.9999. Relative times are frame number divided by 29. The clip has been excerpted, resized and reencoded with audio excluded.

[Teaching notebook and attribution](https://github.com/ada-carter/cv/blob/92e2b961/book/OceanCVLocalizing_YOLO.ipynb) · [Pinned OceanCV video and license](https://huggingface.co/datasets/OceanCV/ROVTransectCompressed/tree/746b1e4dd47a3a8a82a718eb17a44fcb52f0ed8a) · [Pinned annotation archive and license](https://huggingface.co/datasets/OceanCV/EcotypeTransect/tree/b489b0bf0d89044fead694ad8fda85c25aa95bb8) · [Ecotype model card](https://huggingface.co/OceanCV/OOI_Ecotype/blob/94e22c9ad7da1f504004276cfc8461e21a73b644/README.md)

## MBARI Ventana dive V4289

The independent sequence is Benthic Simple from DeepSea-MOT by Kevin Barnard, Elaine Liu, Kristine Walz, Brian Schlining, Nancy Jacobsen Stout and Lonny Lundsten, Monterey Bay Aquarium Research Institute. The original annotation filenames identify ROV Ventana dive V4289 and its July 29, 2020 recording. Three checked filenames across the window share the recording marker 20200729T185027Z. The excerpt offset within the dive recording is undocumented. We retain time relative to this clip. The authors report about 59.94 frames per second. The reference and working clip use the publisher's one-based frame sequence, with selected IDs 1, 61, 121, 181, 241, 301, 361 and 421. The review MP4 is an excerpt of the publisher's video, downscaled to 1280 × 720, reencoded and distributed without audio. The labeled JPEGs retain their original 1920 × 1080 resolution.

MBARI researchers reviewed all 600 frames, fitting boxes to organisms and adding missed animals after an independent detector and tracker generated initial suggestions. In the selected eight frames there are 180 reference boxes and 26 distinct reference track IDs. The 2025 benchmark release postdates Ecotype's January 2025 checkpoint. We checked all 1,776 JPEG hashes in the public Ecotype data against the eight MBARI JPEGs and found zero exact matches. Ecotype uses MBARI-315k as a parent model and the dive was filmed in 2020. Earlier exposure in pretraining cannot be determined from the published records. This is a held-out dive for this comparison. The single 8-second interval is a pilot case, with strong temporal correlation between sampled frames.

The MBARI data, including the MBARI-derived annotations in `reference.json`, and the adapted excerpts and overlays are distributed under Creative Commons Attribution-ShareAlike 4.0. Credit the named creators and MBARI, link the license and describe adaptations such as cropping or reencoding. In the reference file we reformatted the boxes, split the original labels into taxon and track ID and added an ecological crosswalk. [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

[DeepSea-MOT video, JPEGs and annotations](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT/tree/61ecbda8acb2749f3771d7192c51341267da2f37/data/BS) · [Original dive provenance](https://huggingface.co/datasets/MBARI-org/DeepSea-MOT/blob/2163f4bdd04143222f1eebfe618904f765f6c934/data/BS/xml/BS_001.xml) · [Expert review methods](https://arxiv.org/abs/2509.03499)

## Cross-instrument interpretation

Keep the original MBARI taxon, object ID and box. For this trial, sessile epifauna includes Porifera, Sabellidae and Scleractinia. Motile epifauna includes Munida, Ophiuroidea, Rathbunaster californicus, Strongylocentrotus fragilis and Enteroctopus dofleini. Sebastes is mapped to the demersal fish group. The 14 eggcase boxes have no Ecotype class assignment. This ecological crosswalk is a trial convention. Its three mapped groups are only a subset of all organisms that could fall under those broad Ecotype terms. Class-specific precision therefore requires independent review of unmatched detections. The files also retain original expert objectness boxes, allowing class-agnostic localization comparisons.

Where reporting missed boxes or duplicate sightings, state the frame coverage and match rule. Repeated expert boxes for the same track across frames are expected. Report distinct observed tracks using publisher IDs over the sampled interval. Track continuity errors can affect an estimate of individual animals. Neither source provides survey area, distance or effort for an abundance density estimate in this trial.
