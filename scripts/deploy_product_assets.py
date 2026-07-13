#!/usr/bin/env python3
"""Copy image/ assets into static/images/ with ASCII paths.

Run:
  .venv\\Scripts\\python scripts/deploy_product_assets.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEM_TO_KEY = {
    "戒指A": ("ring", "A"),
    "戒指B": ("ring", "B"),
    "戒指C": ("ring", "C"),
    "項墜A": ("pendant", "A"),
    "項墜B": ("pendant", "B"),
    "項墜C": ("pendant", "C"),
    "耳飾A": ("earring", "A"),
    "手鍊A": ("bracelet", "A"),
    "手鍊B": ("bracelet", "B"),
    "手鍊C": ("bracelet", "C"),
    "斗圓鍊K黃": ("chain", "C"),
    "斗圓鍊K玫瑰": ("chain", "B"),
    "斗圓鍊": ("chain", "A"),
}

IMAGE_SOURCES = {
    "white": ROOT / "image" / "silver",
    "rose": ROOT / "image" / "rose_gold",
    "yellow": ROOT / "image" / "gold",
}


def parse_stem(filename: str) -> tuple[str, str] | None:
    stem = Path(filename).stem
    for prefix, key in STEM_TO_KEY.items():
        if stem.startswith(prefix + "_"):
            return key
    return None


def deploy_folder(src: Path, dest_dir: Path, ext: str) -> int:
    if not src.is_dir():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(src.iterdir()):
        if path.suffix.lower() != ext:
            continue
        parsed = parse_stem(path.name)
        if not parsed:
            print(f"  skip (unknown name): {path.name}")
            continue
        category, style = parsed
        out = dest_dir / f"{category}-{style}{ext}"
        shutil.copy2(path, out)
        count += 1
    return count


def main() -> None:
    img_total = 0
    for color, src in IMAGE_SOURCES.items():
        n = deploy_folder(src, ROOT / "static" / "images" / color, ".png")
        print(f"images/{color}: {n} files")
        img_total += n

    print(f"Done — {img_total} images")


if __name__ == "__main__":
    main()
