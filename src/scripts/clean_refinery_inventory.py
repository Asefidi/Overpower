#!/usr/bin/env python3
"""Normalize the legacy refinery workbook into a usable refinery inventory.

The source workbook mixes three different data segments:

1. U.S. refinery rows enriched with EIA Form 820 downstream unit capacities and
   EPA facility emissions/throughput metrics.
2. A thin Mexico/Canada list with only site metadata and crude capacity.
3. A broader international list that looks GEO-like, including `Capacity_C`
   (cubic meters/day) and occasional status values.

This script preserves the raw row, adds interpretation fields, and computes a
low-confidence U.S.-only Nelson-complexity proxy from the recovered EIA unit
columns.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import xlrd


ROOT = Path(__file__).resolve().parents[2]
SOURCE_XLS = ROOT / "src/raw-input-data/US_Mexico_Canada_International_Refineries_Capacity.xls"
OUTPUT_CSV = ROOT / "src/cleaned-data/refinery-inventory-cleaned.csv"
OUTPUT_MAJOR_CSV = ROOT / "src/cleaned-data/refinery-inventory-major.csv"


# Recovered from the official EIA 2017 refinery archive workbook. The original
# workbook had these headers flattened into QUANTITY1..QUANTITY78 during a GIS
#-style pivot/join.
US_UNIT_COLUMN_GROUPS: dict[str, tuple[str, ...]] = {
    "cat_cracking_fresh_feed_bpd": ("QUANTITY1", "QUANTITY2", "QUANTITY3"),
    "cat_hydrocracking_distillate_bpd": ("QUANTITY4", "QUANTITY5", "QUANTITY6"),
    "cat_reforming_high_pressure_bpd": ("QUANTITY7", "QUANTITY8", "QUANTITY9"),
    "cat_hydrocracking_gas_oil_bpd": ("QUANTITY10", "QUANTITY11", "QUANTITY12"),
    "cat_reforming_low_pressure_bpd": ("QUANTITY13", "QUANTITY14", "QUANTITY15"),
    "crude_distillation_operating_bpd": ("QUANTITY16", "QUANTITY17"),
    "desulfurization_diesel_bpd": ("QUANTITY18", "QUANTITY19"),
    "desulfurization_naphtha_reformer_feed_bpd": ("QUANTITY20", "QUANTITY21"),
    "alkylates_bpd": ("QUANTITY22", "QUANTITY23"),
    "aromatics_bpd": ("QUANTITY24", "QUANTITY25"),
    "asphalt_road_oil_bpd": ("QUANTITY26", "QUANTITY27"),
    "idle_crude_capacity_bpd": ("QUANTITY28", "QUANTITY29"),
    "isomerization_isobutane_bpd": ("QUANTITY30", "QUANTITY31"),
    "thermal_cracking_delayed_coking_bpd": ("QUANTITY32", "QUANTITY33", "QUANTITY34"),
    "cat_hydrocracking_residual_bpd": ("QUANTITY35", "QUANTITY36", "QUANTITY37"),
    "desulfurization_other_bpd": ("QUANTITY38", "QUANTITY39"),
    "hydrogen_mmcfd": ("QUANTITY40", "QUANTITY41"),
    "lubricants_bpd": ("QUANTITY42", "QUANTITY43"),
    "crude_distillation_total_operable_bpd": ("QUANTITY44", "QUANTITY45", "QUANTITY46"),
    "cat_cracking_recycled_feed_bpd": ("QUANTITY47", "QUANTITY48"),
    "desulfurization_gasoline_bpd": ("QUANTITY49", "QUANTITY50"),
    "desulfurization_heavy_gas_oil_bpd": ("QUANTITY51", "QUANTITY52"),
    "isomerization_isopentane_isohexane_bpd": ("QUANTITY53", "QUANTITY54"),
    "sulfur_short_tons_per_day": ("QUANTITY55", "QUANTITY56"),
    "isomerization_isooctane_bpd": ("QUANTITY57", "QUANTITY68", "QUANTITY69"),
    "desulfurization_kerosene_jet_bpd": ("QUANTITY58", "QUANTITY59"),
    "desulfurization_other_distillate_bpd": ("QUANTITY60", "QUANTITY61"),
    "vacuum_distillation_bpd": ("QUANTITY62", "QUANTITY63"),
    "fuels_solvent_deasphalting_bpd": ("QUANTITY64", "QUANTITY65"),
    "petcoke_market_bpd": ("QUANTITY66", "QUANTITY67"),
    "thermal_cracking_visbreaking_bpd": ("QUANTITY70", "QUANTITY71"),
    "desulfurization_residual_bpd": ("QUANTITY72", "QUANTITY73"),
    "thermal_cracking_fluid_coking_bpd": ("QUANTITY74", "QUANTITY75", "QUANTITY76"),
    "thermal_cracking_other_bpd": ("QUANTITY77", "QUANTITY78"),
}


# These are intentionally conservative "proxy" factors for a public,
# reproducible approximation. They should be treated as low-confidence inputs,
# not canonical OGJ/Solomon refinery complexity values.
NELSON_PROXY_FACTORS = {
    "vacuum_distillation_bpd": 2.0,
    "cat_cracking_total_bpd": 6.0,
    "cat_hydrocracking_total_bpd": 6.0,
    "cat_reforming_total_bpd": 5.0,
    "hydrotreating_total_bpd": 2.0,
    "coking_total_bpd": 5.5,
    "visbreaking_and_other_thermal_bpd": 2.0,
    "alkylates_bpd": 10.0,
    "isomerization_total_bpd": 3.0,
    "asphalt_road_oil_bpd": 1.5,
    "aromatics_bpd": 8.0,
    "fuels_solvent_deasphalting_bpd": 2.5,
}


US_STATES = {
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
}


def as_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    return "" if text == "." else text


def as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    text = as_text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def max_numeric(row: dict[str, object], columns: tuple[str, ...]) -> float | None:
    values = [as_float(row.get(column)) for column in columns]
    numeric = [value for value in values if value is not None]
    return max(numeric) if numeric else None


def normalize_name(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip().lower())
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def classify_source_segment(country: str) -> str:
    if country == "United States":
        return "us_eia_epa_join"
    if country in {"Canada", "Mexico"}:
        return "north_america_manual_list"
    return "international_geo_like"


def derive_peak_capacity_bpd(row: dict[str, object], country: str) -> float | None:
    raw_capacity = as_float(row.get("Capacity"))
    if country != "United States":
        return raw_capacity

    candidates = [
        raw_capacity,
        max_numeric(row, US_UNIT_COLUMN_GROUPS["crude_distillation_operating_bpd"]),
        max_numeric(row, US_UNIT_COLUMN_GROUPS["crude_distillation_total_operable_bpd"]),
    ]
    numeric = [value for value in candidates if value is not None]
    return max(numeric) if numeric else None


def build_unit_capacity_map(row: dict[str, object]) -> dict[str, float | None]:
    return {
        name: max_numeric(row, columns)
        for name, columns in US_UNIT_COLUMN_GROUPS.items()
    }


def compute_us_nelson_proxy(
    unit_capacities: dict[str, float | None],
    peak_capacity_bpd: float | None,
) -> float | None:
    if not peak_capacity_bpd or peak_capacity_bpd <= 0:
        return None

    cat_cracking_total = sum(
        value or 0.0
        for value in (
            unit_capacities["cat_cracking_fresh_feed_bpd"],
            unit_capacities["cat_cracking_recycled_feed_bpd"],
        )
    )
    cat_hydrocracking_total = sum(
        value or 0.0
        for value in (
            unit_capacities["cat_hydrocracking_distillate_bpd"],
            unit_capacities["cat_hydrocracking_gas_oil_bpd"],
            unit_capacities["cat_hydrocracking_residual_bpd"],
        )
    )
    cat_reforming_total = sum(
        value or 0.0
        for value in (
            unit_capacities["cat_reforming_high_pressure_bpd"],
            unit_capacities["cat_reforming_low_pressure_bpd"],
        )
    )
    hydrotreating_total = sum(
        value or 0.0
        for value in (
            unit_capacities["desulfurization_diesel_bpd"],
            unit_capacities["desulfurization_naphtha_reformer_feed_bpd"],
            unit_capacities["desulfurization_other_bpd"],
            unit_capacities["desulfurization_gasoline_bpd"],
            unit_capacities["desulfurization_heavy_gas_oil_bpd"],
            unit_capacities["desulfurization_kerosene_jet_bpd"],
            unit_capacities["desulfurization_other_distillate_bpd"],
            unit_capacities["desulfurization_residual_bpd"],
        )
    )
    coking_total = sum(
        value or 0.0
        for value in (
            unit_capacities["thermal_cracking_delayed_coking_bpd"],
            unit_capacities["thermal_cracking_fluid_coking_bpd"],
        )
    )
    visbreaking_and_other_thermal = sum(
        value or 0.0
        for value in (
            unit_capacities["thermal_cracking_visbreaking_bpd"],
            unit_capacities["thermal_cracking_other_bpd"],
        )
    )
    isomerization_total = sum(
        value or 0.0
        for value in (
            unit_capacities["isomerization_isobutane_bpd"],
            unit_capacities["isomerization_isopentane_isohexane_bpd"],
            unit_capacities["isomerization_isooctane_bpd"],
        )
    )

    proxy_components = {
        "vacuum_distillation_bpd": unit_capacities["vacuum_distillation_bpd"] or 0.0,
        "cat_cracking_total_bpd": cat_cracking_total,
        "cat_hydrocracking_total_bpd": cat_hydrocracking_total,
        "cat_reforming_total_bpd": cat_reforming_total,
        "hydrotreating_total_bpd": hydrotreating_total,
        "coking_total_bpd": coking_total,
        "visbreaking_and_other_thermal_bpd": visbreaking_and_other_thermal,
        "alkylates_bpd": unit_capacities["alkylates_bpd"] or 0.0,
        "isomerization_total_bpd": isomerization_total,
        "asphalt_road_oil_bpd": unit_capacities["asphalt_road_oil_bpd"] or 0.0,
        "aromatics_bpd": unit_capacities["aromatics_bpd"] or 0.0,
        "fuels_solvent_deasphalting_bpd": unit_capacities["fuels_solvent_deasphalting_bpd"] or 0.0,
    }

    if sum(proxy_components.values()) <= 0:
        return None

    score = 1.0
    for key, factor in NELSON_PROXY_FACTORS.items():
        score += factor * (proxy_components[key] / peak_capacity_bpd)

    rounded = round(score, 2)
    return None if rounded <= 1.1 else rounded


def build_flags(
    row: dict[str, object],
    country: str,
    peak_capacity_bpd: float | None,
    unit_capacities: dict[str, float | None] | None = None,
) -> list[str]:
    flags: list[str] = []
    name = as_text(row.get("Name"))
    company = as_text(row.get("Company"))
    province = as_text(row.get("Prov_State"))
    facility = as_text(row.get("Facility"))

    if facility and facility != "Refinery":
        flags.append("non_refinery_facility_type")

    if country == "United States":
        flags.append("us_structured_segment")
    elif country in {"Canada", "Mexico"}:
        flags.append("north_america_thin_segment")
    else:
        flags.append("international_geo_like_segment")

    if country == "United States" and unit_capacities:
        secondary_capacity = sum(
            value or 0.0
            for key, value in unit_capacities.items()
            if key
            not in {
                "crude_distillation_operating_bpd",
                "crude_distillation_total_operable_bpd",
                "idle_crude_capacity_bpd",
                "hydrogen_mmcfd",
                "sulfur_short_tons_per_day",
            }
        )
        if secondary_capacity <= 0:
            flags.append("missing_us_unit_detail")

    lowered = f"{company} {name}".lower()
    if any(token in lowered for token in ("upgrader", "oil sands", "marine terminal")):
        flags.append("non_refinery_or_upgrader_like")

    if country == "Canada" and province in US_STATES:
        flags.append("likely_country_or_province_error")

    if not as_text(row.get("Capacity_C")) and country not in {"United States", "Canada", "Mexico"}:
        flags.append("missing_international_capacity_c")

    if peak_capacity_bpd is not None and peak_capacity_bpd >= 100_000:
        flags.append("major_refinery")

    if not as_text(row.get("Link")):
        flags.append("missing_link")

    return flags


def main() -> None:
    sheet = xlrd.open_workbook(SOURCE_XLS).sheet_by_index(0)
    header = sheet.row_values(0)
    rows = [dict(zip(header, sheet.row_values(i))) for i in range(1, sheet.nrows)]

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "source_segment",
        "country",
        "state_province",
        "city",
        "facility_type",
        "refinery_name_raw",
        "refinery_name_clean",
        "company_raw",
        "company_clean",
        "site_id",
        "latitude",
        "longitude",
        "capacity_bpd_raw",
        "capacity_m3_day_raw",
        "peak_capacity_bpd",
        "approx_nelson_complexity_proxy",
        "complexity_confidence",
        "status_raw",
        "link_raw",
        "flags",
        "cat_cracking_fresh_feed_bpd",
        "cat_cracking_recycled_feed_bpd",
        "cat_hydrocracking_distillate_bpd",
        "cat_hydrocracking_gas_oil_bpd",
        "cat_hydrocracking_residual_bpd",
        "cat_reforming_high_pressure_bpd",
        "cat_reforming_low_pressure_bpd",
        "vacuum_distillation_bpd",
        "thermal_cracking_delayed_coking_bpd",
        "thermal_cracking_fluid_coking_bpd",
        "thermal_cracking_visbreaking_bpd",
        "thermal_cracking_other_bpd",
        "alkylates_bpd",
        "isomerization_isobutane_bpd",
        "isomerization_isopentane_isohexane_bpd",
        "isomerization_isooctane_bpd",
        "desulfurization_diesel_bpd",
        "desulfurization_naphtha_reformer_feed_bpd",
        "desulfurization_gasoline_bpd",
        "desulfurization_heavy_gas_oil_bpd",
        "desulfurization_kerosene_jet_bpd",
        "desulfurization_other_distillate_bpd",
        "desulfurization_other_bpd",
        "desulfurization_residual_bpd",
        "fuels_solvent_deasphalting_bpd",
        "asphalt_road_oil_bpd",
        "aromatics_bpd",
        "lubricants_bpd",
        "petcoke_market_bpd",
        "hydrogen_mmcfd",
        "sulfur_short_tons_per_day",
    ]

    cleaned_records: list[dict[str, object]] = []

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            country = as_text(row.get("Country"))
            unit_capacities = build_unit_capacity_map(row) if country == "United States" else {}
            peak_capacity_bpd = derive_peak_capacity_bpd(row, country)
            complexity_proxy = (
                compute_us_nelson_proxy(unit_capacities, peak_capacity_bpd)
                if country == "United States"
                else None
            )
            flags = build_flags(row, country, peak_capacity_bpd, unit_capacities or None)

            facility_name = as_text(row.get("Name")) or as_text(row.get("SITE")) or as_text(row.get("City"))
            company_name = as_text(row.get("Company")) or as_text(row.get("COMPANY_NA"))
            site_id = "|".join(
                part
                for part in (
                    normalize_name(country),
                    normalize_name(as_text(row.get("Prov_State"))),
                    normalize_name(facility_name or as_text(row.get("City"))),
                )
                if part
            )

            record = {
                "source_segment": classify_source_segment(country),
                "country": country,
                "state_province": as_text(row.get("Prov_State")),
                "city": as_text(row.get("City")),
                "facility_type": as_text(row.get("Facility")),
                "refinery_name_raw": facility_name,
                "refinery_name_clean": normalize_name(facility_name) if facility_name else "",
                "company_raw": company_name,
                "company_clean": normalize_name(company_name) if company_name else "",
                "site_id": site_id,
                "latitude": as_float(row.get("Latitude")),
                "longitude": as_float(row.get("Longitude")),
                "capacity_bpd_raw": as_float(row.get("Capacity")),
                "capacity_m3_day_raw": as_float(row.get("Capacity_C")),
                "peak_capacity_bpd": peak_capacity_bpd,
                "approx_nelson_complexity_proxy": complexity_proxy,
                "complexity_confidence": "low_proxy" if complexity_proxy is not None else "",
                "status_raw": as_text(row.get("Status")),
                "link_raw": as_text(row.get("Link")),
                "flags": "|".join(flags),
            }

            for unit_name in (
                "cat_cracking_fresh_feed_bpd",
                "cat_cracking_recycled_feed_bpd",
                "cat_hydrocracking_distillate_bpd",
                "cat_hydrocracking_gas_oil_bpd",
                "cat_hydrocracking_residual_bpd",
                "cat_reforming_high_pressure_bpd",
                "cat_reforming_low_pressure_bpd",
                "vacuum_distillation_bpd",
                "thermal_cracking_delayed_coking_bpd",
                "thermal_cracking_fluid_coking_bpd",
                "thermal_cracking_visbreaking_bpd",
                "thermal_cracking_other_bpd",
                "alkylates_bpd",
                "isomerization_isobutane_bpd",
                "isomerization_isopentane_isohexane_bpd",
                "isomerization_isooctane_bpd",
                "desulfurization_diesel_bpd",
                "desulfurization_naphtha_reformer_feed_bpd",
                "desulfurization_gasoline_bpd",
                "desulfurization_heavy_gas_oil_bpd",
                "desulfurization_kerosene_jet_bpd",
                "desulfurization_other_distillate_bpd",
                "desulfurization_other_bpd",
                "desulfurization_residual_bpd",
                "fuels_solvent_deasphalting_bpd",
                "asphalt_road_oil_bpd",
                "aromatics_bpd",
                "lubricants_bpd",
                "petcoke_market_bpd",
                "hydrogen_mmcfd",
                "sulfur_short_tons_per_day",
            ):
                record[unit_name] = unit_capacities.get(unit_name) if unit_capacities else None

            writer.writerow(record)
            cleaned_records.append(record)

    with OUTPUT_MAJOR_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in cleaned_records:
            peak_capacity = record.get("peak_capacity_bpd")
            if isinstance(peak_capacity, (int, float)) and peak_capacity >= 100_000:
                writer.writerow(record)

    print(f"Wrote {OUTPUT_CSV}")
    print(f"Wrote {OUTPUT_MAJOR_CSV}")


if __name__ == "__main__":
    main()
