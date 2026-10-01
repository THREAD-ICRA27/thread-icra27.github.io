#!/usr/bin/env python3
"""Build every web asset under static/ from the raw sources in medias/.

    python3 scripts/build_assets.py            # all assets
    python3 scripts/build_assets.py --only videos|figures|images

Videos: H.264 High, yuv420p, +faststart, no audio, metadata stripped, plus a JPEG
poster taken from the encoded file. Figures (the paper PDFs) and photos: WebP,
metadata stripped. Writes static/assets_manifest.json with the exact pixel size,
fps and frame count of every output; index.html copies those numbers into its
width/height/data-fps/data-frames attributes, and scripts/check_media.py verifies
that they still agree.

ffmpeg: uses `ffmpeg` on PATH, or set FFMPEG=/path/to/ffmpeg (any build with libx264).
"""
import argparse, json, os, re, subprocess, sys, tempfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MED = os.path.join(ROOT, "medias")
# output name -> source path under medias/. Kept in medias/ (not published) so raw file names and
# editing history stay out of the repository.
_SOURCES = os.path.join(MED, "asset_sources.json")
SRC = json.load(open(_SOURCES)) if os.path.exists(_SOURCES) else {}
OUT_V = os.path.join(ROOT, "static", "videos")
OUT_F = os.path.join(ROOT, "static", "figures")
OUT_I = os.path.join(ROOT, "static", "images")
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
ONLY_NAMES = set()

# name: (source, trim_start_s, trim_end_s or None, output width or None, crf, poster_time_s, crop_bottom_rows)
VIDEOS = {
    # video attachment (the overview video): remuxed, not re-encoded -- crf None = stream copy,
    # audio kept, metadata stripped, +faststart
    "attachment":            (SRC["attachment"], 0, None, None, None, 0.5, 0),   # poster = title slide
    # skill library -- the RL insertion clips are 256x256 (60 fps since the 2026-09-30 re-render);
    # upscale x2 (lanczos) so browsers do not blur them further
    "skill_insert_flexible": (SRC["skill_insert_flexible"], 0, None, 512, 20, 3.0, 0),
    "skill_insert_stiff":    (SRC["skill_insert_stiff"], 0, None, 512, 20, 3.0, 0),
    "skill_insert_slide":    (SRC["skill_insert_slide"], 0, None, 512, 20, 3.0, 0),
    "skill_insert_lift":     (SRC["skill_insert_lift"], 0, None, 512, 20, 3.0, 0),
    # Pull and Flatten, cut from the THREAD closed-loop episode so the decision box names the skill
    # for the whole clip (decision 3: pull, decision 7: flatten).
    # The simulation renders carry a 10-row light strip at the bottom; crop it.
    "skill_pull":            (SRC["skill_pull"], 5.35, 8.03, None, 20, 1.0, 10),
    "skill_flatten":         (SRC["skill_flatten"], 12.12, 16.76, None, 20, 1.5, 10),
    # applying the wrong skill
    "wrong_slide_on_bottomed": (SRC["wrong_slide_on_bottomed"], 0, None, 512, 20, 6.0, 0),
    "wrong_stiff_on_flexible": (SRC["wrong_stiff_on_flexible"], 0, None, 512, 20, 8.0, 0),
    # closed loop; the lower-left box shows every planner decision
    "cl_rope_ours":  (SRC["cl_rope_ours"], 0, None, None, 21, 2.0, 10),
    "cl_rope_gpt":   (SRC["cl_rope_gpt"], 0, None, None, 21, 2.0, 10),
    # ends before a render glitch after 32.5 s
    "cl_clip_ours":  (SRC["cl_clip_ours"], 0, 32.5, None, 21, 2.0, 10),
    "cl_clip_gpt":   (SRC["cl_clip_gpt"], 0, None, None, 21, 2.0, 10),
    # real robot
    "real_nylon":    (SRC["real_nylon"], 0, None, 1280, 25, 1.0, 0),
    "real_wire":     (SRC["real_wire"], 0, None, 1280, 25, 1.0, 0),
    # LED-strip routing demo; the last ~2 s (handheld camera move) are cut
    "real_led_demo": (SRC["real_led_demo"], 0, 30.5, 1280, 25, 1.0, 0),
}

# name: (source pdf, output width px)
FIGURES = {
    "fig1_overview":        (SRC["fig1_overview"], 1200),
    "fig2_pipeline":        (SRC["fig2_pipeline"], 2800),
    "fig3_dlos_clips":      (SRC["fig3_dlos_clips"], 1600),
    "fig4_relabel":         (SRC["fig4_relabel"], 2800),
    "fig5_early_flatten":   (SRC["fig5_early_flatten"], 1800),
    "fig6_real_perception": (SRC["fig6_real_perception"], 2800),
}

# name: (source, crop box as fractions (x0, y0, x1, y1) or None, output width or None)
IMAGES = {
    # photos are cropped to the workspace
    "setup_overview":  (SRC["setup_overview"], (0.22, 0.25, 0.92, 0.90), 1600),
    "setup_hands":     (SRC["setup_hands"], (0.0, 0.035, 1.0, 0.965), 1600),
    "cam_world_raw":   (SRC["cam_world_raw"], (0.17, 0.0, 1.0, 0.83), 1600),
    "cam_head":        (SRC["cam_head"], None, 1600),
    "planner_global":  (SRC["planner_global"], None, None),
    "planner_clip":    (SRC["planner_clip"], None, None),
    "fingertip":       (SRC["fingertip"], None, 1600),
    "reach_waist_locked":   (SRC["reach_waist_locked"], None, 900),
    "reach_waist_unlocked": (SRC["reach_waist_unlocked"], None, None),
}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"command failed: {' '.join(cmd)}\n{r.stderr[-1500:]}")
    return r


def probe(path):
    """(width, height, fps, duration) from ffmpeg's banner (no ffprobe needed)."""
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", path], capture_output=True, text=True)
    s = r.stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", s)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})[ ,].*?([\d.]+) fps", s)
    return int(v.group(1)), int(v.group(2)), float(v.group(3)), dur


def count_frames(path):
    # decode to the null muxer; -nostdin, or ffmpeg under a pipe prints no final frame count
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostdin", "-i", path, "-map", "0:v:0", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r"frame=\s*(\d+)", r.stderr)
    return int(m[-1]) if m else None


def build_videos(manifest):
    os.makedirs(OUT_V, exist_ok=True)
    for name, (src, t0, t1, width, crf, poster_t, crop_bottom) in VIDEOS.items():
        if ONLY_NAMES and name not in ONLY_NAMES:
            continue
        inp = os.path.join(MED, src)
        out = os.path.join(OUT_V, name + ".mp4")
        filters = [f"crop=iw:ih-{crop_bottom}:0:0"] if crop_bottom else []
        if width is not None:
            filters.append(f"scale={width}:-2:flags=lanczos")
        filters.append("format=yuv420p")
        vf = ",".join(filters)
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", inp]
        if t0:
            cmd += ["-ss", str(t0)]
        if t1:
            cmd += ["-to", str(t1)]
        if crf is None:       # already a web encode: copy the streams (keeps audio), strip metadata, faststart
            cmd += ["-map", "0:v:0", "-map", "0:a?", "-c", "copy", "-map_metadata", "-1", "-map_metadata:s", "-1",
                    "-map_chapters", "-1", "-movflags", "+faststart", "-fflags", "+bitexact", out]
        else:
            cmd += ["-vf", vf, "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", str(crf),
                    "-movflags", "+faststart", "-an", "-map_metadata", "-1", "-fflags", "+bitexact", out]
        run(cmd)
        w, h, fps, dur = probe(out)
        frames = count_frames(out)
        poster = os.path.join(OUT_V, name + "_poster.jpg")
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(min(poster_t, max(dur - 0.2, 0))),
             "-i", out, "-frames:v", "1", "-q:v", "3", "-map_metadata", "-1", poster])
        manifest[f"videos/{name}.mp4"] = dict(width=w, height=h, fps=round(fps, 3), frames=frames,
                                              duration=round(dur, 2), bytes=os.path.getsize(out),
                                              poster=f"static/videos/{name}_poster.jpg")
        print(f"  video  {name:<26} {w}x{h} {fps:g}fps {frames} frames {os.path.getsize(out)/1e6:5.2f} MB")


def _save_webp(im, out, quality):
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[-1]); im = bg
    else:
        im = im.convert("RGB")
    im.save(out, "WEBP", quality=quality, method=6)      # PIL writes no EXIF unless asked


def build_figures(manifest):
    os.makedirs(OUT_F, exist_ok=True)
    for name, (src, width) in FIGURES.items():
        pdf = os.path.join(MED, src)
        info = run(["pdfinfo", pdf]).stdout
        m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", info)
        dpi = width / (float(m.group(1)) / 72.0)
        with tempfile.TemporaryDirectory() as td:
            run(["pdftoppm", "-r", f"{dpi:.3f}", "-png", "-f", "1", "-l", "1", "-singlefile", pdf, os.path.join(td, "p")])
            im = Image.open(os.path.join(td, "p.png"))
            if im.size[0] != width:
                im = im.resize((width, round(im.size[1] * width / im.size[0])), Image.Resampling.LANCZOS)
            out = os.path.join(OUT_F, name + ".webp")
            _save_webp(im, out, 90)
            w, h = Image.open(out).size
        manifest[f"figures/{name}.webp"] = dict(width=w, height=h, bytes=os.path.getsize(out))
        print(f"  figure {name:<26} {w}x{h} {os.path.getsize(out)/1e3:7.0f} KB")


def build_images(manifest):
    os.makedirs(OUT_I, exist_ok=True)
    for name, (src, crop, width) in IMAGES.items():
        im = Image.open(os.path.join(MED, src))
        im.load()
        if crop:
            W, H = im.size
            im = im.crop((round(crop[0] * W), round(crop[1] * H), round(crop[2] * W), round(crop[3] * H)))
        if width and im.size[0] > width:
            im = im.resize((width, round(im.size[1] * width / im.size[0])), Image.Resampling.LANCZOS)
        out = os.path.join(OUT_I, name + ".webp")
        _save_webp(im, out, 86)
        w, h = Image.open(out).size
        manifest[f"images/{name}.webp"] = dict(width=w, height=h, bytes=os.path.getsize(out))
        print(f"  image  {name:<26} {w}x{h} {os.path.getsize(out)/1e3:7.0f} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["videos", "figures", "images"])
    ap.add_argument("--names", nargs="*", help="rebuild only these video names")
    a = ap.parse_args()
    global ONLY_NAMES
    ONLY_NAMES = set(a.names or [])
    mpath = os.path.join(ROOT, "static", "assets_manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    if a.only in (None, "figures"):
        build_figures(manifest)
    if a.only in (None, "images"):
        build_images(manifest)
    if a.only in (None, "videos"):
        build_videos(manifest)
    json.dump(dict(sorted(manifest.items())), open(mpath, "w"), indent=1)
    total = sum(v["bytes"] for v in manifest.values())
    print(f"manifest: {len(manifest)} assets, {total/1e6:.1f} MB -> {mpath}")


if __name__ == "__main__":
    main()
