#!/usr/bin/env python3
"""Generate thumbnails and refresh the README gallery section.

Called by GitHub Actions after the wallpapers are downloaded; can also
be run manually:
    python3 make_gallery.py

- Thumbnails go to thumbs/ (400px wide); only images without one are
  processed
- The section of README.md between <!-- GALLERY-START --> and
  <!-- GALLERY-END --> is rewritten every run:
  * the latest month is shown expanded as a thumbnail grid
    (4 per row, click a thumbnail to open the full image; every
    cell also carries a "download 4k" link, like
    github.com/niumoo/bing-wallpaper — but pointing at this
    repo's raw file URL, the same URL as the download button
    on GitHub's file page, so it saves the file directly
    instead of opening the file page)
  * earlier months are folded into <details> blocks, expanded only
    when the month title is clicked, so the README stays fast to
    open no matter how many images accumulate
- A second generated section, between <!-- ARCHIVES-START --> and
  <!-- ARCHIVES-END --> (appended at the end of README.md when the
  markers are not there yet), lists every completed month with a
  direct-download link to that month's zip in Releases — the
  monthly-archive workflow publishes tag YYYY-MM with asset
  bing-wallpapers-YYYY-MM.zip on the 1st of each month. The
  current, still-running month is not listed: its zip does not
  exist yet, so the link would be dead.
- Images live in monthly subfolders pics/YYYY-MM/ (the downloader
  creates them automatically). Any legacy image still sitting
  flat in pics/ is moved into its month subfolder on each run,
  so the folder tidies itself up without a manual migration.
"""
import calendar
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parent
PICS = ROOT / "pics"
THUMBS = ROOT / "thumbs"
README = ROOT / "README.md"
START, END = "<!-- GALLERY-START -->", "<!-- GALLERY-END -->"
A_START, A_END = "<!-- ARCHIVES-START -->", "<!-- ARCHIVES-END -->"
THUMB_W = 400
COLS = 4


# Prefix for the "download 4k" links; main() upgrades it to the
# repo's absolute raw URL when the slug can be determined.
DL_BASE = "pics/"


def repo_slug() -> str:
    """The repo's owner/name slug, or "" when it cannot be told.

    Comes from the GITHUB_REPOSITORY env var in Actions, or from
    the local git remote otherwise.
    """
    slug = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" in slug:
        return slug
    try:
        url = subprocess.check_output(
            ["git", "-C", str(ROOT), "config", "--get",
             "remote.origin.url"],
            text=True, stderr=subprocess.DEVNULL).strip()
        url = url.rstrip("/").removesuffix(".git")
        parts = [p for p in url.replace(":", "/").split("/") if p]
        slug = "/".join(parts[-2:]) if len(parts) >= 2 else ""
    except Exception:
        slug = ""
    return slug if "/" in slug else ""


def raw_base() -> str:
    """Raw-download base URL for pics/ on GitHub.

    The /raw/refs/heads/<branch>/ URL is the one behind the
    download button on a file page: GitHub serves it as an
    attachment, so the browser saves the image instead of
    opening its page. Falls back to a plain relative link when
    the repo slug is unknown.
    """
    slug = repo_slug()
    if not slug:
        return "pics/"
    branch = os.environ.get("GITHUB_REF_NAME", "").strip() or "main"
    return f"https://github.com/{slug}/raw/refs/heads/{branch}/pics/"


def archives_for(months, keys) -> str:
    """The 'Monthly archives' section: one direct-download link
    per completed month, pointing at the zip the monthly-archive
    workflow publishes in Releases (tag YYYY-MM, asset
    bing-wallpapers-YYYY-MM.zip — clicking downloads the zip
    straight away, no intermediate page)."""
    now_key = datetime.now(timezone.utc).strftime("%Y%m")
    done = [k for k in keys if k < now_key]
    parts = ["## Monthly archives\n\n"
             "Every completed month's wallpapers bundled as one zip "
             "in Releases — click a month to download it directly:"]
    if not done:
        parts.append("_No archives yet — the first monthly zip is "
                     "published in Releases on the 1st of next month._")
    slug = repo_slug()
    for k in done:
        ym = f"{k[:4]}-{k[4:]}"
        label = f"{month_label(k)} · {len(months[k])} images"
        if slug:
            url = (f"https://github.com/{slug}/releases/download/"
                   f"{ym}/bing-wallpapers-{ym}.zip")
            parts.append(f"- [{label}]({url})")
        else:
            parts.append(f"- {label}")
    return "\n\n".join(parts)


def month_label(key: str) -> str:
    return f"{calendar.month_name[int(key[4:])]} {key[:4]}"


def rel_url(p: Path) -> str:
    """Path of an image below pics/, URL-quoted, keeping the
    monthly subfolder: '2026-11/20261117_title.jpg'."""
    return quote(p.relative_to(PICS).as_posix())


def table_for(files) -> str:
    cells = []
    for p in files:
        date = f"{p.name[:4]}-{p.name[4:6]}-{p.name[6:8]}"
        rel = rel_url(p)
        cells.append(
            f"[![{date}](thumbs/{quote(p.name)})](pics/{rel})"
            f"<br>{date} [download 4k]({DL_BASE}{rel})")
    rows = []
    for i in range(0, len(cells), COLS):
        chunk = cells[i:i + COLS]
        chunk += [""] * (COLS - len(chunk))
        rows.append("| " + " | ".join(chunk) + " |")
    return "| | | | |\n|---|---|---|---|\n" + "\n".join(rows)


def main() -> int:
    global DL_BASE
    DL_BASE = raw_base()
    THUMBS.mkdir(exist_ok=True)
    # Legacy tidy-up: move any image still flat in pics/ into its
    # monthly subfolder pics/YYYY-MM/ (month taken from the
    # YYYYMMDD filename prefix). Idempotent; an image already in
    # place in the subfolder is never overwritten.
    if PICS.exists():
        for p in sorted(PICS.glob("*.jpg")):
            if len(p.name) >= 6 and p.name[:6].isdigit():
                target_dir = PICS / f"{p.name[:4]}-{p.name[4:6]}"
                target = target_dir / p.name
                if not target.exists():
                    target_dir.mkdir(parents=True, exist_ok=True)
                    p.rename(target)
    files = sorted(PICS.rglob("*.jpg"), reverse=True) if PICS.exists() else []
    for p in files:
        t = THUMBS / p.name
        if t.exists() and t.stat().st_size > 5_000:
            continue
        with Image.open(p) as im:
            im = im.convert("RGB")
            w, h = im.size
            im.resize((THUMB_W, max(1, int(h * THUMB_W / w)))).save(
                t, quality=82)

    months = {}
    for p in files:
        months.setdefault(p.name[:6], []).append(p)
    keys = sorted(months, reverse=True)

    if not keys:
        gallery = "_No images yet_"
    else:
        parts = []
        latest = keys[0]
        parts.append(
            f"### {month_label(latest)} (latest month)\n\n"
            + table_for(months[latest]))
        for k in keys[1:]:
            label = f"{month_label(k)} · {len(months[k])} images"
            parts.append(
                f"<details>\n<summary>{label} (click to expand)</summary>\n\n"
                + table_for(months[k]) + "\n\n</details>")
        gallery = "\n\n".join(parts)

    text = README.read_text(encoding="utf-8")
    pre, sep, rest = text.partition(START)
    if not sep:
        raise SystemExit("GALLERY markers not found in README.md")
    _, _, post = rest.partition(END)
    text = pre + START + "\n\n" + gallery + "\n\n" + END + post

    block = A_START + "\n\n" + archives_for(months, keys) + "\n\n" + A_END
    if A_START in text:
        pre, _, rest = text.partition(A_START)
        _, _, post = rest.partition(A_END)
        text = pre + block + post
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    README.write_text(text, encoding="utf-8")
    print(f"gallery updated: {len(files)} images, {len(keys)} months")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
