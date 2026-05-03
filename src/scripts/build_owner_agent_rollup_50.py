#!/usr/bin/env python3

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_DATA_PATH = ROOT / "src/raw-input-data/Global-Oil-and-Gas-Extraction-Tracker-March-2026__Field-level_main_data.csv"
PRODUCTION_DATA_PATH = ROOT / "src/raw-input-data/Global-Oil-and-Gas-Extraction-Tracker-March-2026__Field-level_production_data.csv"
OUTPUT_PATH = ROOT / "src/cleaned-data/owner-agent-country-rollup-50.csv"

TOP_COMPANY_COUNT = 20
REPRESENTATIVE_AGENT_LIMIT = 50
OIL_FUELS = {"oil", "crude oil", "oil and condensate", "crude oil and condensate"}

SHARE_RE = re.compile(r"^(.*?)\s*\[\s*([0-9]+(?:\.[0-9]+)?)%\s*\]\s*$")
TRAILING_SHARE_RE = re.compile(r"\s*\[[^\]]*\]\s*$")

ENTITY_ALIAS_OVERRIDES = {
    "Apache": "APA Corp",
    "BP P.L.C.": "BP PLC",
    "Burlington Resources O & G Co LP": "ConocoPhillips Corp",
    "COG Operating LLC": "ConocoPhillips Corp",
    "Chevron USA Inc": "Chevron Corp",
    "China Petroleum and Natural Gas Group LTD Xinjiang Oilfield Co": "PetroChina Co Ltd",
    "Chrysaor Ltd": "Harbour Energy PLC",
    "Equinor Energy AS": "Equinor ASA",
    "NNPC E&P Ltd": "NNPC Ltd",
    "Nigerian Agip Oil Company Ltd": "Eni SpA",
    "PetroChina Changqing Oilfield Branch Co": "PetroChina Co Ltd",
    "PetroChina Southwest Oil & Gasfield Co": "PetroChina Co Ltd",
    "Petrochina Talimu Oilfield Company Co Ltd": "PetroChina Co Ltd",
    "Petronas Carigali Sdn Bhd": "Petroliam Nasional Bhd",
    "The Shell Petroleum Development Company of Nigeria Ltd": "Shell PLC",
    "TotalEnergies E&P UK Ltd": "TotalEnergies SE",
    "TotalEnergies EP Nigeria Ltd": "TotalEnergies SE",
    "Wintershall Dea GmbH": "Harbour Energy PLC",
    "Wintershall Dea Norge AS": "Harbour Energy PLC",
    "XTO Energy Inc": "Exxon Mobil Corp",
}

ENTITY_CANONICAL_PATTERNS = (
    (r"^abu dhabi national oil\b|^adnoc\b", "Abu Dhabi National Oil Co"),
    (r"^apa\b|^apache\b", "APA Corp"),
    (r"^bp\b", "BP PLC"),
    (r"^chevron\b", "Chevron Corp"),
    (r"^cnooc\b", "CNOOC Ltd"),
    (r"^conocophillips\b", "ConocoPhillips Corp"),
    (r"^eni\b", "Eni SpA"),
    (r"^equinor\b", "Equinor ASA"),
    (r"^exxon mobil\b", "Exxon Mobil Corp"),
    (r"^gazprom neft\b", "Gazprom Neft PJSC"),
    (r"^gazprom\b", "Gazprom PJSC"),
    (r"^harbour energy\b|^wintershall dea\b|^chrysaor\b", "Harbour Energy PLC"),
    (r"^lukoil\b|^pjsc lukoil\b", "LUKOIL PJSC"),
    (r"^nnpc\b", "NNPC Ltd"),
    (r"^occidental\b|^oxy\b", "Occidental Petroleum Corp"),
    (r"^petrochina\b", "PetroChina Co Ltd"),
    (r"^petroleo brasileiro\b|^petroleos brasileiro\b", "Petróleo Brasileiro SA"),
    (r"^petroleos mexicanos\b|^pemex\b", "Petróleos Mexicanos EPE"),
    (r"^petroliam nasional\b|^petronas\b", "Petroliam Nasional Bhd"),
    (r"^qatarenergy\b", "QatarEnergy"),
    (r"^repsol\b", "Repsol SA"),
    (r"^rosneft\b", "Rosneft PJSC"),
    (r"^shell\b", "Shell PLC"),
    (r"^totalenergies\b", "TotalEnergies SE"),
)

COUNTRY_DEMONYMS = {
    "Algeria": "Algerian",
    "Angola": "Angolan",
    "Argentina": "Argentine",
    "Australia": "Australian",
    "Azerbaijan": "Azerbaijani",
    "Brazil": "Brazilian",
    "Brunei": "Bruneian",
    "Canada": "Canadian",
    "Chad": "Chadian",
    "China": "Chinese",
    "Colombia": "Colombian",
    "Denmark": "Danish",
    "Ecuador": "Ecuadorian",
    "Egypt": "Egyptian",
    "Gabon": "Gabonese",
    "Germany": "German",
    "Guyana": "Guyanese",
    "India": "Indian",
    "Indonesia": "Indonesian",
    "Iran": "Iranian",
    "Iraq": "Iraqi",
    "Kazakhstan": "Kazakh",
    "Kuwait": "Kuwaiti",
    "Libya": "Libyan",
    "Malaysia": "Malaysian",
    "Mexico": "Mexican",
    "Nigeria": "Nigerian",
    "Norway": "Norwegian",
    "Oman": "Omani",
    "Pakistan": "Pakistani",
    "Qatar": "Qatari",
    "Republic of the Congo": "Congolese",
    "Russia": "Russian",
    "Saudi Arabia": "Saudi",
    "South Sudan": "South Sudanese",
    "Syria": "Syrian",
    "Thailand": "Thai",
    "Turkmenistan": "Turkmen",
    "Türkiye": "Turkish",
    "United Arab Emirates": "Emirati",
    "United Kingdom": "British",
    "United States": "American",
    "Uzbekistan": "Uzbek",
    "Venezuela": "Venezuelan",
    "Yemen": "Yemeni",
}

COUNTRY_KEY_OVERRIDES = {
    "United Arab Emirates": "uae",
    "United Kingdom": "uk",
    "United States": "usa",
}

ENTITY_KEY_OVERRIDES = {
    "Abu Dhabi National Oil Co": "adnoc",
    "BP PLC": "bp",
    "Exxon Mobil Corp": "exxon-mobil",
    "LUKOIL PJSC": "lukoil",
    "NNPC Ltd": "nnpc",
    "Petróleo Brasileiro SA": "petrobras",
    "Petróleos Mexicanos EPE": "pemex",
    "Petróleos de Venezuela SA": "pdvsa",
    "Saudi Arabian Oil Co": "aramco",
}

ENTITY_SUFFIXES = {
    "ab",
    "ag",
    "asa",
    "as",
    "bv",
    "co",
    "company",
    "corp",
    "corporation",
    "epe",
    "gmbh",
    "holding",
    "holdings",
    "inc",
    "jsc",
    "limited",
    "ltd",
    "nv",
    "oy",
    "pjsc",
    "plc",
    "sa",
    "saa",
    "se",
    "spa",
}


def normalize_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("&", " and ")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def slugify(text: str) -> str:
    return normalize_ascii(text).replace(" ", "-")


def parse_ownership_items(cell: str) -> list[tuple[str, float | None]]:
    items: list[tuple[str, float | None]] = []
    for raw_item in (cell or "").split(";"):
        raw_item = raw_item.strip()
        if not raw_item:
            continue
        match = SHARE_RE.match(raw_item)
        if match:
            items.append((match.group(1).strip(), float(match.group(2))))
            continue
        items.append((TRAILING_SHARE_RE.sub("", raw_item).strip(), None))
    return items


def build_alias_map() -> dict[str, str]:
    alias_counts: Counter[tuple[str, str]] = Counter()
    with MAIN_DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            owners = parse_ownership_items(row["Owner(s)"])
            parents = parse_ownership_items(row["Parent(s)"])
            if len(owners) == 1 and len(parents) == 1:
                owner_name = owners[0][0]
                parent_name = parents[0][0]
                if owner_name and parent_name and owner_name != parent_name:
                    alias_counts[(owner_name, parent_name)] += 1
    alias_map = {owner: parent for (owner, parent), count in alias_counts.items() if count >= 2}
    alias_map.update(ENTITY_ALIAS_OVERRIDES)
    return alias_map


def canonicalize_entity(name: str, alias_map: dict[str, str]) -> str:
    candidate = alias_map.get(name, name)
    normalized = normalize_ascii(candidate)
    for pattern, canonical in ENTITY_CANONICAL_PATTERNS:
        if re.search(pattern, normalized):
            return canonical
    return candidate


def normalize_weights(items: list[tuple[str, float | None]]) -> list[tuple[str, float]]:
    known_total = sum(weight for _, weight in items if weight is not None)
    missing_count = sum(1 for _, weight in items if weight is None)

    if known_total <= 0 and missing_count == len(items):
        return [(name, 1.0 / len(items)) for name, _ in items]

    if missing_count and 0 < known_total < 100:
        fill_value = (100 - known_total) / missing_count
        filled = [(name, weight if weight is not None else fill_value) for name, weight in items]
    else:
        filled = [(name, weight or 0.0) for name, weight in items]

    total = sum(weight for _, weight in filled)
    if total <= 0:
        return [(name, 1.0 / len(items)) for name, _ in items]

    return [(name, weight / total) for name, weight in filled]


def choose_ownership_entities(row: dict[str, str]) -> list[tuple[str, float]]:
    owners = parse_ownership_items(row["Owner(s)"])
    parents = parse_ownership_items(row["Parent(s)"])

    if parents and any(weight is not None for _, weight in parents):
        return normalize_weights(parents)
    if owners and any(weight is not None for _, weight in owners):
        return normalize_weights(owners)
    if owners:
        return normalize_weights(owners)
    if parents:
        return normalize_weights(parents)
    return []


def load_crude_production_by_unit() -> dict[str, float]:
    production_by_unit: dict[str, float] = {}
    with PRODUCTION_DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            fuel = (row["Fuel description"] or "").strip().lower()
            if fuel not in OIL_FUELS:
                continue
            try:
                quantity = float(row["Quantity (converted)"])
            except (TypeError, ValueError):
                continue
            production_by_unit[row["Unit ID"]] = quantity
    return production_by_unit


def country_key(country: str) -> str:
    return COUNTRY_KEY_OVERRIDES.get(country, slugify(country))


def country_misc_bucket(country: str) -> tuple[str, str]:
    demonym = COUNTRY_DEMONYMS.get(country)
    if demonym:
        return f"misc-{demonym}", f"misc-{slugify(demonym)}"
    return f"misc-{country}", f"misc-{slugify(country)}"


def entity_bucket_key(entity: str) -> str:
    if entity in ENTITY_KEY_OVERRIDES:
        return ENTITY_KEY_OVERRIDES[entity]

    tokens = normalize_ascii(entity).split()
    while tokens and tokens[-1] in ENTITY_SUFFIXES:
        tokens.pop()
    return "-".join(tokens) if tokens else slugify(entity)


def build_rollup() -> list[dict[str, object]]:
    alias_map = build_alias_map()
    crude_production_by_unit = load_crude_production_by_unit()

    entity_totals: Counter[str] = Counter()
    entity_country_totals: defaultdict[str, Counter[str]] = defaultdict(Counter)
    unit_records: list[dict[str, object]] = []

    with MAIN_DATA_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            unit_id = row["Unit ID"]
            crude_production = crude_production_by_unit.get(unit_id)
            if crude_production is None:
                continue

            weighted_entities = choose_ownership_entities(row)
            if not weighted_entities:
                continue

            asset_country = row["Country/Area"]
            for raw_entity, weight in weighted_entities:
                entity = canonicalize_entity(raw_entity, alias_map)
                weighted_crude = crude_production * weight
                entity_totals[entity] += weighted_crude
                entity_country_totals[entity][asset_country] += weighted_crude
                unit_records.append(
                    {
                        "unit_id": unit_id,
                        "asset_country": asset_country,
                        "entity": entity,
                        "weighted_crude": weighted_crude,
                    }
                )

    top_entities = {entity for entity, _ in entity_totals.most_common(TOP_COMPANY_COUNT)}

    misc_country_totals: Counter[str] = Counter()
    entity_home_country: dict[str, str] = {}
    for entity, country_totals in entity_country_totals.items():
        if entity in top_entities:
            continue
        home_country, _ = country_totals.most_common(1)[0]
        entity_home_country[entity] = home_country
        misc_country_totals[home_country] += entity_totals[entity]

    misc_slots = REPRESENTATIVE_AGENT_LIMIT - TOP_COMPANY_COUNT
    if len(misc_country_totals) > misc_slots:
        kept_misc_countries = {country for country, _ in misc_country_totals.most_common(misc_slots - 1)}
        use_misc_other = True
    else:
        kept_misc_countries = set(misc_country_totals)
        use_misc_other = False

    bucket_metadata: dict[str, dict[str, object]] = {}
    for entity in top_entities:
        dominant_country, _ = entity_country_totals[entity].most_common(1)[0]
        bucket_key = entity_bucket_key(entity)
        bucket_metadata[bucket_key] = {
            "representative_agent": entity,
            "representative_agent_key": bucket_key,
            "bucket_type": "top20_company",
            "bucket_basis_country": dominant_country,
            "agent_country_key": f"{bucket_key}-{country_key(dominant_country)}",
            "assigned_country": dominant_country,
        }

    for country in kept_misc_countries:
        bucket_name, bucket_key = country_misc_bucket(country)
        bucket_metadata[bucket_key] = {
            "representative_agent": bucket_name,
            "representative_agent_key": bucket_key,
            "bucket_type": "misc_country",
            "bucket_basis_country": country,
            "agent_country_key": f"{bucket_key}-{country_key(country)}",
            "assigned_country": country,
        }

    if use_misc_other:
        bucket_metadata["misc-other"] = {
            "representative_agent": "misc-Other",
            "representative_agent_key": "misc-other",
            "bucket_type": "misc_other",
            "bucket_basis_country": "Other",
            "agent_country_key": "misc-other-other",
            "assigned_country": "Other",
        }

    if len(bucket_metadata) > REPRESENTATIVE_AGENT_LIMIT:
        raise RuntimeError(f"Built {len(bucket_metadata)} representative agents; expected at most {REPRESENTATIVE_AGENT_LIMIT}.")

    rows_by_key: dict[str, dict[str, object]] = {}
    for record in unit_records:
        entity = record["entity"]  # type: ignore[assignment]
        asset_country = record["asset_country"]  # type: ignore[assignment]
        unit_id = record["unit_id"]  # type: ignore[assignment]
        weighted_crude = float(record["weighted_crude"])

        if entity in top_entities:
            bucket_key = entity_bucket_key(entity)
        else:
            home_country = entity_home_country[entity]
            if home_country in kept_misc_countries:
                _, bucket_key = country_misc_bucket(home_country)
            else:
                bucket_key = "misc-other"

        metadata = bucket_metadata[bucket_key]
        aggregate = rows_by_key.setdefault(
            bucket_key,
            {
                "agent_country_key": metadata["agent_country_key"],
                "representative_agent": metadata["representative_agent"],
                "representative_agent_key": metadata["representative_agent_key"],
                "bucket_type": metadata["bucket_type"],
                "bucket_basis_country": metadata["bucket_basis_country"],
                "assigned_country": metadata["assigned_country"],
                "weighted_crude_production_million_bbl_y": 0.0,
                "unit_ids": set(),
                "source_entities": set(),
                "source_asset_countries": set(),
            },
        )
        aggregate["weighted_crude_production_million_bbl_y"] += weighted_crude
        aggregate["unit_ids"].add(unit_id)
        aggregate["source_entities"].add(entity)
        aggregate["source_asset_countries"].add(asset_country)

    rows: list[dict[str, object]] = []
    for aggregate in rows_by_key.values():
        rows.append(
            {
                "agent_country_key": aggregate["agent_country_key"],
                "representative_agent": aggregate["representative_agent"],
                "representative_agent_key": aggregate["representative_agent_key"],
                "bucket_type": aggregate["bucket_type"],
                "bucket_basis_country": aggregate["bucket_basis_country"],
                "assigned_country": aggregate["assigned_country"],
                "weighted_crude_production_million_bbl_y": round(
                    float(aggregate["weighted_crude_production_million_bbl_y"]), 6
                ),
                "unit_count": len(aggregate["unit_ids"]),
                "source_entity_count": len(aggregate["source_entities"]),
                "source_asset_country_count": len(aggregate["source_asset_countries"]),
            }
        )

    rows.sort(
        key=lambda row: (
            row["bucket_type"] != "top20_company",
            -float(row["weighted_crude_production_million_bbl_y"]),
            str(row["representative_agent"]),
            str(row["assigned_country"]),
        )
    )
    return rows


def write_output(rows: list[dict[str, object]]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "agent_country_key",
        "representative_agent",
        "representative_agent_key",
        "bucket_type",
        "bucket_basis_country",
        "assigned_country",
        "weighted_crude_production_million_bbl_y",
        "unit_count",
        "source_entity_count",
        "source_asset_country_count",
    ]
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_rollup()
    write_output(rows)
    representative_agent_count = len({row["representative_agent_key"] for row in rows})
    total_weighted_crude = sum(float(row["weighted_crude_production_million_bbl_y"]) for row in rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")
    print(f"Representative agents: {representative_agent_count}")
    print(f"Total weighted crude production (million bbl/y): {total_weighted_crude:.3f}")


if __name__ == "__main__":
    main()
