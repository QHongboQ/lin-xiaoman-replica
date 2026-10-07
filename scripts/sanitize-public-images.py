#!/usr/bin/env python3
"""Copy a reviewed image directory into a public-safe, metadata-clean folder.

This intentionally assigns new sequential filenames. Review the source images
first; this script is not a privacy or copyright classifier.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageSequence


FORMATS = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}


def sanitize_image(source: Path, target: Path) -> None:
    image = Image.open(source)
    image_format = image.format
    if image_format not in FORMATS:
        raise ValueError(f"Unsupported image format: {image_format}")

    if image_format == "JPEG":
        image.load()
        image.convert("RGB").save(
            target,
            format="JPEG",
            quality=95,
            optimize=True,
            exif=b"",
            icc_profile=None,
            comment=None,
        )
    elif image_format == "PNG":
        image.save(target, format="PNG", optimize=True, pnginfo=None, exif=b"")
    elif image_format == "WEBP":
        image.save(target, format="WEBP", quality=95, exif=b"", xmp=b"", icc_profile=None)
    else:
        loop = int(image.info.get("loop", 0))
        transparency = image.info.get("transparency")
        durations: list[int] = []
        frames = []
        for frame in ImageSequence.Iterator(image):
            durations.append(int(frame.info.get("duration", 100)))
            cleaned = frame.copy()
            cleaned.info.clear()
            frames.append(cleaned)
        frames[0].save(
            target,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=loop,
            disposal=2,
            optimize=False,
            transparency=transparency,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--prefix", default="image")
    parser.add_argument(
        "--exclude-indexes",
        default="",
        help="Comma-separated 1-based indexes to omit from sorted source files after review.",
    )
    args = parser.parse_args()
    excluded = {int(value) for value in args.exclude_indexes.split(",") if value.strip()}
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    sources = sorted(
        path
        for path in args.source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for index, source in enumerate(sources, start=1):
        if index in excluded:
            continue
        image = Image.open(source)
        suffix = FORMATS.get(image.format or "")
        if suffix is None:
            continue
        target = args.output_dir / f"{args.prefix}-{written + 1:04}.{suffix}"
        sanitize_image(source, target)
        written += 1

    print(f"Wrote {written} reviewed images to {args.output_dir}")


if __name__ == "__main__":
    main()
