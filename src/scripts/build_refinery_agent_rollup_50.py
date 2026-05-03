#!/usr/bin/env python3

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "src/cleaned-data/refinery-inventory-cleaned.csv"
OUTPUT_PATH = ROOT / "src/cleaned-data/refinery-agent-country-rollup-50.csv"

TOP_COMPANY_COUNT = 20
REPRESENTATIVE_AGENT_LIMIT = 50
MISC_PREFIX = "misc"

EXCLUDED_FLAGS = {
    "likely_country_or_province_error",
    "non_refinery_or_upgrader_like",
    "non_refinery_facility_type",
}

ENTITY_ALIAS_OVERRIDES = {
    "ALON ISRAEL OIL COMPANY LTD": "Alon",
    "BP PLC": "BP",
    "CHEVRON CORP": "Chevron",
    "CONOCOPHILLIPS": "ConocoPhillips",
    "ExxonMobil": "Exxon Mobil",
    "EXXON MOBIL CORP": "Exxon Mobil",
    "Essar Energy": "Essar",
    "Imperial": "Imperial Oil",
    "Imperial Oil": "Imperial Oil",
    "IOCL": "IOCL",
    "KOCH INDUSTRIES INC": "Koch",
    "MARATHON PETROLEUM CORP": "Marathon",
    "MOTIVA ENTERPRISES LLC": "Motiva",
    "Nroth Atlantic Refining Limited": "North Atlantic",
    "ONGC": "ONGC",
    "PDV AMERICA INC": "Citgo/PDV",
    "Pemex": "Pemex",
    "Petrobras": "Petrobras",
    "Reliance Industries": "Reliance",
    "ROYAL DUTCH/SHELL GROUP": "Shell",
    "Shell Oil Products US": "Shell",
    "Suncor Energy Inc": "Suncor",
    "TESORO CORP": "Tesoro",
    "Ultramar (Valero)": "Valero",
    "VALERO ENERGY CORP": "Valero",
}

ENTITY_CANONICAL_PATTERNS = (
    (r"^adnoc\b|^abu dhabi national oil\b", "ADNOC"),
    (r"^alon\b", "Alon"),
    (r"^bashneft\b", "Bashneft"),
    (r"^bp\b", "BP"),
    (r"^bpcl\b", "BPCL"),
    (r"^caltex\b|^chevron\b", "Chevron"),
    (r"^chinese petroleum corporation\b|^cpc\b", "CPC"),
    (r"^citgo\b", "Citgo/PDV"),
    (r"^cncp\b|^cnpc\b|^petrochina\b", "CNPC/PetroChina"),
    (r"^conocophillips\b", "ConocoPhillips"),
    (r"^co op\b|^co-op\b", "Co-op"),
    (r"^cpcl\b", "CPCL"),
    (r"^eni\b", "ENI"),
    (r"^essar\b", "Essar"),
    (r"^esso\b|^exxon ?mobil\b", "Exxon Mobil"),
    (r"^hanwha\b", "Hanwha"),
    (r"^hpcl\b", "HPCL"),
    (r"^hyundai\b", "Hyundai"),
    (r"^iocl\b", "IOCL"),
    (r"^imperial\b", "Imperial Oil"),
    (r"^irving\b", "Irving"),
    (r"^isab\b", "ISAB"),
    (r"^knpc\b", "KNPC"),
    (r"^lg-caltex\b", "LG-Caltex"),
    (r"^lukoil\b", "LUKOIL"),
    (r"^marathon\b", "Marathon"),
    (r"^motiva\b", "Motiva"),
    (r"^mrpl\b", "MRPL"),
    (r"^nprc\b", "NPRC"),
    (r"^ongc\b", "ONGC"),
    (r"^pdvsa\b", "PDVSA"),
    (r"^pemex\b", "Pemex"),
    (r"^pertamina\b", "Pertamina"),
    (r"^petrobras\b", "Petrobras"),
    (r"^petronas\b", "Petronas"),
    (r"^phillips 66\b", "Phillips 66"),
    (r"^reliance\b|^rpl\b", "Reliance"),
    (r"^repsol\b", "Repsol"),
    (r"^s-oil\b", "S-Oil"),
    (r"^saudi aramco\b", "Saudi Aramco"),
    (r"^saras\b", "Saras"),
    (r"^shell\b", "Shell"),
    (r"^sinopec\b", "Sinopec"),
    (r"^sk corp\b", "SK Corp"),
    (r"^slavneft\b", "Slavneft"),
    (r"^suncor\b", "Suncor"),
    (r"^syncrude\b", "Syncrude"),
    (r"^tesoro\b", "Tesoro"),
    (r"^total\b|^totalfinaelf\b", "Total"),
    (r"^tnk-bp\b|^tnk-bpl\b", "TNK-BP"),
    (r"^ultramar\b|^valero\b", "Valero"),
    (r"^wepec\b", "WEPEC"),
    (r"^yukos\b", "Yukos"),
)

TRAILING_LOCATION_TOKENS = (
    "Argentina",
    "Bulgaria",
    "Belgium",
    "Greece",
    "India",
    "Italy",
    "Norway",
    "Pakistan",
    "Thailand",
    "Turkey",
    "UAE",
    "UK",
)

COUNTRY_DEMONYMS = {
    "Algeria": "Algerian",
    "Argentina": "Argentine",
    "Australia": "Australian",
    "Azerbaijan": "Azerbaijani",
    "Brazil": "Brazilian",
    "Canada": "Canadian",
    "China": "Chinese",
    "Egypt": "Egyptian",
    "Germany": "German",
    "Greece": "Greek",
    "India": "Indian",
    "Indonesia": "Indonesian",
    "Iraq": "Iraqi",
    "Italy": "Italian",
    "Japan": "Japanese",
    "Kazakhstan": "Kazakh",
    "Kuwait": "Kuwaiti",
    "Malaysia": "Malaysian",
    "Mexico": "Mexican",
    "Netherlands": "Dutch",
    "Nigeria": "Nigerian",
    "Poland": "Polish",
    "Republic of China Taiwan": "Taiwanese",
    "Republic of Korea": "Korean",
    "Romania": "Romanian",
    "Russian Federation": "Russian",
    "Saudi Arabia": "Saudi",
    "Singapore": "Singaporean",
    "Spain": "Spanish",
    "Sweden": "Swedish",
    "Turkey": "Turkish",
    "Ukraine": "Ukrainian",
    "United Arab Emirates": "Emirati",
    "United Kingdom": "British",
    "United States": "American",
    "Venezuela": "Venezuelan",
}

COUNTRY_KEY_OVERRIDES = {
    "Republic of China Taiwan": "taiwan",
    "Republic of Korea": "south-korea",
    "Russian Federation": "russia",
    "United Arab Emirates": "uae",
    "United Kingdom": "uk",
    "United States": "usa",
}

COUNTRY_COMPLEXITY_BUMPS = {
    "China": 0.5,
    "France": 0.5,
    "Germany": 0.5,
    "India": 1.0,
    "Japan": 1.0,
    "Kuwait": 1.0,
    "Netherlands": 0.5,
    "Republic of China Taiwan": 1.0,
    "Republic of Korea": 1.0,
    "Saudi Arabia": 1.0,
    "Singapore": 1.0,
    "Spain": 0.5,
    "United Arab Emirates": 1.0,
    "United Kingdom": 0.5,
    "United States": 1.0,
}


def normalize_ascii(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.replace("&", " and ")
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def slugify(text: str) -> str:
    return normalize_ascii(text).replace(" ", "-")


def country_key(country: str) -> str:
    return COUNTRY_KEY_OVERRIDES.get(country, slugify(country))


def country_demonym(country: str) -> str:
    return COUNTRY_DEMONYMS.get(country, country)


def as_float(value: str) -> float:
    return float(value or 0)


def round_or_blank(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def clean_inferred_entity(name: str) -> str:
    candidate = (name or "").strip()
    candidate = re.sub(r"\bRefinery\b.*$", "", candidate, flags=re.IGNORECASE).strip(" ,-")
    for token in TRAILING_LOCATION_TOKENS:
        candidate = re.sub(rf"\b{re.escape(token)}\b$", "", candidate).strip(" ,-")
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate


def infer_entity_name(row: dict[str, str]) -> str:
    company_raw = (row["company_raw"] or "").strip()
    if company_raw:
        candidate = ENTITY_ALIAS_OVERRIDES.get(company_raw, company_raw)
    else:
        candidate = clean_inferred_entity(row["refinery_name_raw"])

    normalized = normalize_ascii(candidate)
    for pattern, canonical in ENTITY_CANONICAL_PATTERNS:
        if re.search(pattern, normalized):
            return canonical

    if not candidate:
        return "Unknown"
    parts = candidate.split()
    return " ".join(parts[:3]) if len(parts) > 3 else candidate


def representative_agent_key(agent: str) -> str:
    return slugify(agent)


def misc_agent(country: str) -> str:
    return f"{MISC_PREFIX}-{country_demonym(country)}"


def include_row(row: dict[str, str]) -> bool:
    if as_float(row["peak_capacity_bpd"]) <= 0:
        return False
    row_flags = set(flag for flag in row["flags"].split("|") if flag)
    return not (row_flags & EXCLUDED_FLAGS)


def choose_dominant_country(capacity_by_country: dict[str, float]) -> str:
    return max(capacity_by_country.items(), key=lambda item: (item[1], item[0]))[0]


def capacity_weighted_average(pairs: list[tuple[float, float]]) -> float | None:
    total_weight = sum(weight for _, weight in pairs if weight > 0)
    if total_weight <= 0:
        return None
    weighted_sum = sum(value * weight for value, weight in pairs if weight > 0)
    return weighted_sum / total_weight


def direct_site_complexity(row: dict[str, str]) -> float | None:
    raw = row.get("approx_nelson_complexity_proxy", "")
    return float(raw) if raw else None


def capacity_complexity_baseline(capacity_bpd: float) -> float:
    if capacity_bpd < 50_000:
        return 4.0
    if capacity_bpd < 100_000:
        return 5.5
    if capacity_bpd < 200_000:
        return 7.0
    if capacity_bpd < 350_000:
        return 8.5
    if capacity_bpd < 500_000:
        return 10.0
    return 11.0


def estimate_site_complexity(
    row: dict[str, object],
    entity_complexity_defaults: dict[str, float],
) -> tuple[float, str]:
    direct = direct_site_complexity(row)  # type: ignore[arg-type]
    if direct is not None:
        return direct, "direct_us_proxy"

    entity = str(row["entity"])
    if entity in entity_complexity_defaults:
        return entity_complexity_defaults[entity], "entity_imputed"

    country = str(row["country"])
    capacity = float(row["capacity"])
    estimated = capacity_complexity_baseline(capacity) + COUNTRY_COMPLEXITY_BUMPS.get(country, 0.0)
    estimated = max(3.0, min(15.0, estimated))
    return estimated, "capacity_country_imputed"


def product_yield_profile(complexity_score: float) -> tuple[float, float, float]:
    if complexity_score < 5:
        return 0.22, 0.24, 0.05
    if complexity_score < 7:
        return 0.28, 0.26, 0.06
    if complexity_score < 9:
        return 0.34, 0.27, 0.07
    if complexity_score < 11:
        return 0.40, 0.28, 0.08
    if complexity_score < 13:
        return 0.45, 0.30, 0.09
    return 0.48, 0.31, 0.10


def main() -> None:
    with INPUT_PATH.open(newline="", encoding="utf-8") as handle:
        input_rows = [row for row in csv.DictReader(handle) if include_row(row)]

    rows: list[dict[str, object]] = []
    entity_total_capacity: defaultdict[str, float] = defaultdict(float)
    entity_country_capacity: defaultdict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    entity_known_complexity_pairs: defaultdict[str, list[tuple[float, float]]] = defaultdict(list)

    for row in input_rows:
        entity = infer_entity_name(row)
        country = row["country"]
        capacity = as_float(row["peak_capacity_bpd"])

        enriched = dict(row)
        enriched["entity"] = entity
        enriched["capacity"] = capacity
        rows.append(enriched)

        entity_total_capacity[entity] += capacity
        entity_country_capacity[entity][country] += capacity
        direct_complexity = direct_site_complexity(row)
        if direct_complexity is not None:
            entity_known_complexity_pairs[entity].append((direct_complexity, capacity))

    entity_complexity_defaults = {
        entity: value
        for entity, value in (
            (
                entity,
                capacity_weighted_average(pairs),
            )
            for entity, pairs in entity_known_complexity_pairs.items()
        )
        if value is not None
    }

    top_entities = {
        entity
        for entity, _ in sorted(
            entity_total_capacity.items(),
            key=lambda item: (-item[1], item[0]),
        )[:TOP_COMPANY_COUNT]
    }

    entity_global_rank = {
        entity: rank
        for rank, (entity, _) in enumerate(
            sorted(
                entity_total_capacity.items(),
                key=lambda item: (-item[1], item[0]),
            ),
            start=1,
        )
    }

    bucket_rows: dict[str, dict[str, object]] = {}
    misc_member_entities: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        entity = row["entity"]  # type: ignore[assignment]
        source_country = row["country"]  # type: ignore[assignment]
        capacity = row["capacity"]  # type: ignore[assignment]
        site_complexity, complexity_source = estimate_site_complexity(row, entity_complexity_defaults)
        gasoline_yield, diesel_yield, jet_yield = product_yield_profile(site_complexity)
        gasoline_capacity = float(capacity) * gasoline_yield
        diesel_capacity = float(capacity) * diesel_yield
        jet_capacity = float(capacity) * jet_yield

        if entity in top_entities:
            assigned_country = source_country
            representative_agent = entity
            bucket_type = "top20_company_country"
            bucket_basis_country = source_country
        else:
            assigned_country = choose_dominant_country(entity_country_capacity[entity])  # type: ignore[index]
            representative_agent = misc_agent(assigned_country)
            bucket_type = "misc_country"
            bucket_basis_country = assigned_country

        agent_key = representative_agent_key(str(representative_agent))
        agent_country_key = f"{agent_key}-{country_key(str(assigned_country))}"

        if agent_country_key not in bucket_rows:
            bucket_rows[agent_country_key] = {
                "agent_country_key": agent_country_key,
                "representative_agent": representative_agent,
                "representative_agent_key": agent_key,
                "bucket_type": bucket_type,
                "bucket_basis_country": bucket_basis_country,
                "assigned_country": assigned_country,
                "total_peak_capacity_bpd": 0.0,
                "capacity_weighted_complexity_sum": 0.0,
                "known_complexity_capacity_bpd": 0.0,
                "imputed_complexity_capacity_bpd": 0.0,
                "approx_complexity_score": "",
                "complexity_confidence": "",
                "approx_gasoline_capacity_bpd": 0.0,
                "approx_diesel_capacity_bpd": 0.0,
                "approx_jet_capacity_bpd": 0.0,
                "source_site_count": 0,
                "source_entity_count": 0,
                "source_asset_country_count": 0,
                "top20_company_rank": entity_global_rank.get(entity, ""),
                "entity_global_capacity_bpd": round(entity_total_capacity[entity], 3),
                "member_entities_preview": "",
            }

        bucket = bucket_rows[agent_country_key]
        bucket["total_peak_capacity_bpd"] = round(float(bucket["total_peak_capacity_bpd"]) + float(capacity), 3)
        bucket["capacity_weighted_complexity_sum"] = round(
            float(bucket["capacity_weighted_complexity_sum"]) + float(capacity) * site_complexity,
            6,
        )
        bucket["approx_gasoline_capacity_bpd"] = round(
            float(bucket["approx_gasoline_capacity_bpd"]) + gasoline_capacity,
            3,
        )
        bucket["approx_diesel_capacity_bpd"] = round(
            float(bucket["approx_diesel_capacity_bpd"]) + diesel_capacity,
            3,
        )
        bucket["approx_jet_capacity_bpd"] = round(
            float(bucket["approx_jet_capacity_bpd"]) + jet_capacity,
            3,
        )
        bucket["source_site_count"] = int(bucket["source_site_count"]) + 1
        if complexity_source == "direct_us_proxy":
            bucket["known_complexity_capacity_bpd"] = round(
                float(bucket["known_complexity_capacity_bpd"]) + float(capacity),
                3,
            )
        else:
            bucket["imputed_complexity_capacity_bpd"] = round(
                float(bucket["imputed_complexity_capacity_bpd"]) + float(capacity),
                3,
            )

        entity_set = bucket.setdefault("_entity_set", set())
        entity_set.add(entity)
        country_set = bucket.setdefault("_country_set", set())
        country_set.add(source_country)

        if bucket_type == "misc_country":
            misc_member_entities[agent_country_key][entity] += float(capacity)

    for key, bucket in bucket_rows.items():
        entity_set = bucket.pop("_entity_set")
        country_set = bucket.pop("_country_set")
        bucket["source_entity_count"] = len(entity_set)
        bucket["source_asset_country_count"] = len(country_set)
        total_capacity = float(bucket["total_peak_capacity_bpd"])
        weighted_complexity_sum = float(bucket.pop("capacity_weighted_complexity_sum"))
        complexity_score = weighted_complexity_sum / total_capacity if total_capacity > 0 else None
        bucket["approx_complexity_score"] = round_or_blank(complexity_score)
        known_capacity = float(bucket["known_complexity_capacity_bpd"])
        if known_capacity >= total_capacity * 0.75:
            bucket["complexity_confidence"] = "medium"
        elif known_capacity > 0:
            bucket["complexity_confidence"] = "medium-low"
        else:
            bucket["complexity_confidence"] = "low"

        if bucket["bucket_type"] == "misc_country":
            preview = [
                entity
                for entity, _ in misc_member_entities[key].most_common(8)
            ]
            bucket["member_entities_preview"] = "; ".join(preview)
            bucket["top20_company_rank"] = ""
            bucket["entity_global_capacity_bpd"] = ""
        else:
            bucket["member_entities_preview"] = next(iter(entity_set))

    sorted_buckets = sorted(
        bucket_rows.values(),
        key=lambda row: (-float(row["total_peak_capacity_bpd"]), row["agent_country_key"]),
    )[:REPRESENTATIVE_AGENT_LIMIT]

    fieldnames = [
        "agent_country_key",
        "representative_agent",
        "representative_agent_key",
        "bucket_type",
        "bucket_basis_country",
        "assigned_country",
        "total_peak_capacity_bpd",
        "approx_complexity_score",
        "complexity_confidence",
        "known_complexity_capacity_bpd",
        "imputed_complexity_capacity_bpd",
        "approx_gasoline_capacity_bpd",
        "approx_diesel_capacity_bpd",
        "approx_jet_capacity_bpd",
        "source_site_count",
        "source_entity_count",
        "source_asset_country_count",
        "top20_company_rank",
        "entity_global_capacity_bpd",
        "member_entities_preview",
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted_buckets)

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
