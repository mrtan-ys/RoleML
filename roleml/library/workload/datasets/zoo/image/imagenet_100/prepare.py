#!/usr/bin/env python3
"""Download and verify the ImageNet-100 (CMC subset) dataset.

Downloads the pre-curated CMC ImageNet-100 from Hugging Face Hub and
verifies the on-disk layout matches the expected class list.

Dataset source: https://huggingface.co/datasets/asafaa/imagenet100-cmc
Class list: CMC (Tian et al. 2019, arXiv:1906.05849)

Usage:
    pip install huggingface_hub
    python -m impl.workload.datasets.imagenet100.prepare ~/datasets/imagenet-100
"""

import argparse
import sys
import zipfile
from pathlib import Path


def load_expected_wnids(target: Path) -> list[str]:
    synsets_file = target / "selected_synsets.txt"
    if not synsets_file.is_file():
        print(f"ERROR: {synsets_file} not found (download may have failed)", file=sys.stderr)
        sys.exit(1)
    return [line.strip() for line in synsets_file.read_text().splitlines() if line.strip()]


def download(target: Path) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is required. Install with: pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)

    print(f"Downloading asafaa/imagenet100-cmc to {target} ...")
    snapshot_download(repo_id="asafaa/imagenet100-cmc", repo_type="dataset", local_dir=str(target))
    print("Download complete.")


def extract(target: Path) -> None:
    zips = sorted(target.glob("*.zip"))
    if not zips:
        print("No zip files found to extract.")
        return

    already_extracted = (target / "train").is_dir() and (target / "val").is_dir()
    if already_extracted:
        print(f"Extracted data already present, skipping {len(zips)} zip files.")
        return

    print(f"Extracting {len(zips)} zip files ...")
    for i, zp in enumerate(zips, 1):
        print(f"  [{i}/{len(zips)}] {zp.name}")
        with zipfile.ZipFile(zp, "r") as zf:
            zf.extractall(target)
    print("Extraction complete.")


def verify(target: Path) -> None:
    expected = set(load_expected_wnids(target))

    for split in ("train", "val"):
        split_dir = target / split
        if not split_dir.is_dir():
            print(f"ERROR: missing split directory {split_dir}", file=sys.stderr)
            sys.exit(1)

        found = {p.name for p in split_dir.iterdir() if p.is_dir()}
        missing = expected - found
        extra = found - expected

        if missing:
            print(f"ERROR: {split}/ missing {len(missing)} expected WNIDs: {sorted(missing)[:5]} ...", file=sys.stderr)
            sys.exit(1)
        if extra:
            print(f"WARNING: {split}/ has {len(extra)} unexpected directories: {sorted(extra)[:5]} ...")

        n_images = sum(1 for _ in split_dir.rglob("*") if _.is_file())
        print(f"  {split}: {len(found)} classes, {n_images} files")

    print(f"OK: layout matches CMC class list ({len(expected)} classes).")


def main():
    parser = argparse.ArgumentParser(description="Prepare ImageNet-100 (CMC) dataset.")
    parser.add_argument("target", type=Path, help="output directory for the dataset")
    parser.add_argument("--skip-download", action="store_true", help="skip download, only verify")
    args = parser.parse_args()

    target = args.target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    if not args.skip_download:
        download(target)

    extract(target)

    verify(target)


if __name__ == "__main__":
    main()
