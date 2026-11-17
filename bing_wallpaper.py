#!/usr/bin/env python3
"""Download Bing daily wallpapers (4K UHD, falls back to 1080p).

Images are stored in a monthly subfolder of the output directory,
named YYYY-MM after the image's own date (created automatically),
e.g. pics/2026-11/20261117_title.jpg.

Usage:
    python bing_wallpaper.py            # today only
    python bing_wallpaper.py 8          # the last 8 days
    python bing_wallpaper.py 8 -o D:/Pictures/Bing
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

API = "https://www.bing.com/HPImageArchive.aspx?format=js&idx={idx}&n={n}&mkt=zh-CN"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:60]


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 50_000:
            return False
        dest.write_bytes(data)
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("count", nargs="?", type=int, default=1, help="how many recent days to download (1-8)")
    ap.add_argument("-o", "--out", default="BingWallpapers", help="output directory")
    args = ap.parse_args()

    count = max(1, min(args.count, 8))
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    images = fetch_json(API.format(idx=0, n=8))["images"][:count]
    ok = 0
    for img in images:
        stem = safe(f"{img['startdate']}_{img.get('title', 'bing')}")
        month_dir = out_dir / f"{img['startdate'][:4]}-{img['startdate'][4:6]}"
        month_dir.mkdir(parents=True, exist_ok=True)
        dest = month_dir / f"{stem}.jpg"
        legacy = out_dir / f"{stem}.jpg"   # old flat layout, pre-subfolders
        if (dest.exists() and dest.stat().st_size > 50_000) or \
                (legacy.exists() and legacy.stat().st_size > 50_000):
            print(f"Skip (already exists): {dest.name}")
            ok += 1
            continue
        for suffix in ("_UHD.jpg", "_1920x1080.jpg"):
            if download("https://www.bing.com" + img["urlbase"] + suffix, dest):
                size = dest.stat().st_size
                print(f"Saved: {dest.name}  ({size / 1024 / 1024:.1f} MB)  {img.get('copyright', '')}")
                ok += 1
                break
        else:
            print(f"Failed: {img['startdate']}", file=sys.stderr)

    print(f"\nDone {ok}/{len(images)}, dir: {out_dir.resolve()}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
