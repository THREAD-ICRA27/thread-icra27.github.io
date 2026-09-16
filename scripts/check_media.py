#!/usr/bin/env python3
"""Verify every <video>/<img> in index.html against the files it points to.

    python3 scripts/check_media.py

Checks, for each video: the <source> and poster exist, width/height match the
encoded file, and data-fps/data-frames match (from static/assets_manifest.json,
written by build_assets.py). For each image: the file exists and width/height
match its pixels. Also checks that every video has width/height (so its box is
reserved before load) and that autoplaying clips are muted. Exit code 1 on any
problem. Run it after editing index.html or re-building assets.
"""
import html.parser, json, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Collect(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.videos, self.images, self._v = [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "video":
            self._v = dict(a, _line=self.getpos()[0], _src=None)
            self.videos.append(self._v)
        elif tag == "source" and self._v is not None:
            self._v["_src"] = a.get("src")
        elif tag == "img":
            self.images.append(dict(a, _line=self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag == "video":
            self._v = None


def main():
    page = os.path.join(ROOT, "index.html")
    c = Collect(); c.feed(open(page, encoding="utf-8").read())
    mpath = os.path.join(ROOT, "static", "assets_manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    problems = []

    for v in c.videos:
        where = f"index.html:{v['_line']}"
        src = v.get("_src")
        if not src:
            problems.append(f"{where} video has no <source src>"); continue
        if not os.path.exists(os.path.join(ROOT, src)):
            problems.append(f"{where} missing video file {src}")
        poster = v.get("poster")
        if not poster or not os.path.exists(os.path.join(ROOT, poster)):
            problems.append(f"{where} missing poster {poster}")
        if not (v.get("width") and v.get("height")):
            problems.append(f"{where} {src} has no width/height (its box is not reserved before load)")
        if "data-autoplay" in v and "muted" not in v:
            problems.append(f"{where} {src} autoplays but is not muted (browsers will block it)")
        m = manifest.get(src.replace("static/", "", 1))
        if not m:
            problems.append(f"{where} {src} is not in assets_manifest.json (re-run build_assets.py)"); continue
        if (str(m["width"]), str(m["height"])) != (v.get("width"), v.get("height")):
            problems.append(f"{where} {src} width/height {v.get('width')}x{v.get('height')} != file {m['width']}x{m['height']}")
        if "data-fps" in v:
            if abs(float(v["data-fps"]) - m["fps"]) > 0.01:
                problems.append(f"{where} {src} data-fps {v['data-fps']} != file {m['fps']}")
            if int(v.get("data-frames", -1)) != m["frames"]:
                problems.append(f"{where} {src} data-frames {v.get('data-frames')} != file {m['frames']}")
        if poster and os.path.exists(os.path.join(ROOT, poster)):
            pw, ph = Image.open(os.path.join(ROOT, poster)).size
            if abs(pw / ph - m["width"] / m["height"]) > 0.01:
                problems.append(f"{where} poster {poster} aspect {pw}x{ph} differs from the video")

    for i in c.images:
        where = f"index.html:{i['_line']}"
        src = i.get("src", "")
        path = os.path.join(ROOT, src)
        if not os.path.exists(path):
            problems.append(f"{where} missing image {src}"); continue
        w, h = Image.open(path).size
        if (str(w), str(h)) != (i.get("width"), i.get("height")):
            problems.append(f"{where} {src} width/height {i.get('width')}x{i.get('height')} != file {w}x{h}")

    print(f"checked {len(c.videos)} videos and {len(c.images)} images")
    for p in problems:
        print("  PROBLEM:", p)
    print("PASS" if not problems else f"FAIL ({len(problems)} problems)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
