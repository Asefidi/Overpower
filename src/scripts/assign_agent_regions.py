#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = ROOT / "src" / "cleaned-data"
TARGET_FILES = (
    "crude-agent-country-rollup-50.csv",
    "refinery-agent-country-rollup-50.csv",
)

VALID_REGIONS = {
    "NORTHCOM",
    "CHINA",
    "EUCOM",
    "RUSSIA",
    "IRAN",
    "INDOPACOM",
    "CENTCOM",
    "AFRICOM",
    "SOUTHCOM",
}

COUNTRY_ALIASES = {
    "Islamic Republic of Iran": "Iran",
    "Republic of China Taiwan": "Taiwan",
    "Republic of Korea": "South Korea",
    "Russian Federation": "Russia",
    "Türkiye": "Turkey",
}

COUNTRY_REGION_MAP = {
    "Algeria": "AFRICOM",
    "Angola": "AFRICOM",
    "Argentina": "SOUTHCOM",
    "Australia": "INDOPACOM",
    "Azerbaijan": "EUCOM",
    "Brazil": "SOUTHCOM",
    "Canada": "NORTHCOM",
    "China": "CHINA",
    "Colombia": "SOUTHCOM",
    "Ecuador": "SOUTHCOM",
    "Egypt": "CENTCOM",
    "France": "EUCOM",
    "Germany": "EUCOM",
    "Guyana": "SOUTHCOM",
    "India": "INDOPACOM",
    "Indonesia": "INDOPACOM",
    "Iran": "IRAN",
    "Iraq": "CENTCOM",
    "Italy": "EUCOM",
    "Japan": "INDOPACOM",
    "Kazakhstan": "CENTCOM",
    "Kuwait": "CENTCOM",
    "Libya": "AFRICOM",
    "Malaysia": "INDOPACOM",
    "Mexico": "NORTHCOM",
    "Netherlands": "EUCOM",
    "Nigeria": "AFRICOM",
    "Norway": "EUCOM",
    "Oman": "CENTCOM",
    "Qatar": "CENTCOM",
    "Russia": "RUSSIA",
    "Saudi Arabia": "CENTCOM",
    "Singapore": "INDOPACOM",
    "South Korea": "INDOPACOM",
    "South Sudan": "AFRICOM",
    "Spain": "EUCOM",
    "Taiwan": "INDOPACOM",
    "Thailand": "INDOPACOM",
    "Turkey": "EUCOM",
    "Ukraine": "EUCOM",
    "United Arab Emirates": "CENTCOM",
    "United Kingdom": "EUCOM",
    "United States": "NORTHCOM",
    "Venezuela": "SOUTHCOM",
}


def canonical_country(raw_country: str) -> str:
    stripped = (raw_country or "").strip()
    return COUNTRY_ALIASES.get(stripped, stripped)


def assign_region(country: str, default_region: str | None, strict: bool) -> str:
    normalized_country = canonical_country(country)
    region = COUNTRY_REGION_MAP.get(normalized_country)
    if region:
        return region
    if strict:
        raise KeyError(normalized_country)
    return default_region or ""


def process_file(
    input_path: Path,
    output_path: Path,
    *,
    country_column: str,
    default_region: str | None,
    strict: bool,
) -> set[str]:
    with input_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"No header found in {input_path}")

        fieldnames = list(reader.fieldnames)
        if country_column not in fieldnames:
            raise ValueError(f"Missing required column '{country_column}' in {input_path}")
        if "region" not in fieldnames:
            fieldnames.append("region")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        unmapped: set[str] = set()
        with output_path.open("w", newline="", encoding="utf-8") as out_handle:
            writer = csv.DictWriter(out_handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                raw_country = row.get(country_column, "")
                normalized_country = canonical_country(raw_country)
                if normalized_country not in COUNTRY_REGION_MAP:
                    unmapped.add(normalized_country)
                try:
                    row["region"] = assign_region(raw_country, default_region, strict)
                except KeyError:
                    row["region"] = default_region or ""
                writer.writerow(row)
    return unmapped


def output_path_for(input_path: Path, in_place: bool) -> Path:
    if in_place:
        return input_path
    return input_path.with_name(f"{input_path.stem}-with-region{input_path.suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assign one of the nine Overpower regions to crude/refinery agent rollups "
            "using the assigned_country column."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing cleaned rollups (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite source CSVs instead of writing '*-with-region.csv' files.",
    )
    parser.add_argument(
        "--default-region",
        default="INDOPACOM",
        help="Region used for unmapped countries unless --strict is enabled (default: INDOPACOM).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when an assigned_country value is not mapped.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    default_region = (args.default_region or "").strip()
    if default_region and default_region not in VALID_REGIONS:
        raise ValueError(
            f"Invalid --default-region '{default_region}'. Expected one of: {sorted(VALID_REGIONS)}"
        )

    if args.strict:
        default_region = None

    all_unmapped: set[str] = set()
    for name in TARGET_FILES:
        input_path = args.input_dir / name
        if not input_path.exists():
            raise FileNotFoundError(f"Missing input file: {input_path}")
        output_path = output_path_for(input_path, args.in_place)
        unmapped = process_file(
            input_path=input_path,
            output_path=output_path,
            country_column="assigned_country",
            default_region=default_region,
            strict=args.strict,
        )
        all_unmapped.update(unmapped)
        print(f"Wrote {output_path}")

    if all_unmapped:
        print(
            "Warning: unmapped countries received "
            f"{default_region!r}: {', '.join(sorted(all_unmapped))}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
