# THREAD project page

Project page for the ICRA 2027 submission *THREAD: Task-Specific Hierarchical
Reasoning for Adaptive DLO Routing*. It is **anonymous** while the paper is under
double-anonymous review: no author names, no affiliations, no link to the review PDF,
`noindex` in the `<head>`.

One static page (`index.html`) plus `static/`. No build step for the page itself, no
external scripts, no analytics. Layout adapted from the Academic Project Page Template
(Nerfies-derived, CC BY-SA 4.0); the only third-party file is `static/css/bulma.min.css`
(MIT).

## Page sections

| Anchor | Content |
|---|---|
| `#video` | video attachment (**placeholder** until the ICRA video is ready) |
| `#abstract` | abstract and Fig. 1 |
| `#overview` | pipeline (Fig. 2) |
| `#skills` | skill library clips, DLO/clip types (Fig. 3), wrong-skill clips, skill transfer table |
| `#data` | oracle data collection and flattening relabeling (Fig. 4) |
| `#closed-loop` | THREAD vs zero-shot GPT closed-loop videos, early flattening (Fig. 5), Table IV |
| `#real` | real-robot trial videos, perception pipeline (Fig. 6), setup photos |
| `#gallery` | reachability maps and supplementary tables not in the paper |
| `#bibtex` | anonymous BibTeX |

## Layout

```
index.html                  the page
static/css/index.css        page styles
static/js/index.js          play clips while on screen, frame scrubber, copy BibTeX
static/figures/*.webp       paper figures rendered from medias/paper_figs/*.pdf
static/images/*.webp        setup photos and reachability maps (privacy-cropped)
static/videos/*.mp4         H.264 web encodes + *_poster.jpg
static/assets_manifest.json pixel size / fps / frame count of every asset
scripts/build_assets.py     medias/ -> static/ (ffmpeg, pdftoppm, Pillow)
scripts/check_media.py      index.html attributes vs the actual files
scripts/qa_page.py          headless-Chrome check: layout shift, overflow, playable media, screenshots
scripts/qa_tiles.py         cut a full-page screenshot into readable tiles
scripts/qa_layout_shift.py  layout shift at load and while scrolling, under real device emulation
medias/                     raw sources (git-ignored, not published)
robots.txt                  keeps crawlers out of static/ during the review period
```

## Replacing the video attachment

Encode the attachment to H.264 MP4 (for example with the `encode` settings in
`scripts/build_assets.py`), put it at `static/videos/attachment.mp4` with a poster
`static/videos/attachment_poster.jpg`, then edit the `<video>` in the `#video` section:
`src`, `poster`, `width` and `height` (the file's pixel size). If the attachment has
audio, keep the `controls` attribute and do not add `muted`/`data-autoplay`.

## Rebuilding assets and checking the page

```
FFMPEG=/path/to/ffmpeg python3 scripts/build_assets.py      # or --only videos|figures|images
python3 scripts/check_media.py                              # must print PASS
python3 scripts/qa_page.py . qa_out                         # no overflow, all media playable, screenshots
python3 scripts/qa_layout_shift.py . 390 3                  # layout shift must be 0 (repeat for other widths)
```

Every `<video>` and `<img>` carries `width`/`height` equal to the file's pixel size so the
browser reserves its box before loading, and every clip has a poster. The scrubber slot
(`<div class="scrub">`) is written in the HTML so the page does not shift when the script
fills it. Keep both conventions when adding media.

`qa_page.py` lays out widths below 500 px inside an iframe (headless Chrome will not open a
narrower window); its layout-shift number there is unreliable, so use `qa_layout_shift.py`,
which emulates the device directly.

## Before publishing

1. **Anonymity.** Serve from an account or organization whose name does not identify an
   author (a GitHub Pages URL contains the account name), and commit with a neutral git
   identity (`git config user.name` / `user.email` in this repository are set to neutral
   values). Repository history is public.
2. **Never commit `medias/`.** It holds the raw sources and is git-ignored.
3. **Links.** The `Paper` and `Code` buttons are placeholders (`is-pending`); turn them into
   links when the camera-ready PDF and code exist.
4. **After review.** Add authors and affiliations to the header, update the BibTeX, and
   remove `<meta name="robots" content="noindex, nofollow">` and `robots.txt`.
