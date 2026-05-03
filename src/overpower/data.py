from __future__ import annotations

import csv
from collections import defaultdict
from math import sqrt
from pathlib import Path

from .sim import (
    BASE_PRODUCT_PRICES,
    DEFAULT_SPR_INVENTORY_BBL,
    HOUSEHOLD_QUARTILES,
    PRODUCTS,
    SPR_STORAGE_CAPACITY_BBL,
    CrudeProducerAgent,
    DemandAgent,
    LocalityState,
    PolicyControls,
    RefineryAgent,
    RouteState,
    ScenarioPreset,
    SimulationConfig,
    WorldState,
    step_world,
)

ROOT = Path(__file__).resolve().parents[2]
CORE_DATA_PATH = ROOT / "src" / "raw-input-data" / "core-data.csv"
CRUDE_AGENT_PATH = ROOT / "src" / "cleaned-data" / "crude-agent-country-rollup-50-with-region.csv"
REFINERY_AGENT_PATH = ROOT / "src" / "cleaned-data" / "refinery-agent-country-rollup-50-with-region.csv"
OIL_CONSUMPTION_PATH = ROOT / "src" / "raw-input-data" / "oil-consumption.csv"
OIL_PRODUCTION_PATH = ROOT / "src" / "raw-input-data" / "oil-production-country.csv"

NODE_IDS = (
    "NORTHCOM",
    "EUCOM",
    "RUSSIA",
    "CENTCOM",
    "IRAN",
    "CHINA",
    "INDOPACOM",
    "AFRICOM",
    "SOUTHCOM",
)

LOCALITY_LABELS = {node_id: node_id.replace("_", " ") for node_id in NODE_IDS}

LOCALITY_POSITIONS = {
    "NORTHCOM": (0.15, 0.23),
    "EUCOM": (0.40, 0.22),
    "RUSSIA": (0.56, 0.16),
    "CENTCOM": (0.60, 0.36),
    "IRAN": (0.67, 0.35),
    "CHINA": (0.82, 0.24),
    "INDOPACOM": (0.81, 0.56),
    "AFRICOM": (0.44, 0.56),
    "SOUTHCOM": (0.18, 0.76),
}

COUNTRY_ALIASES = {
    "Islamic Republic of Iran": "Iran",
    "Other": "Other",
    "Republic of China Taiwan": "Taiwan",
    "Republic of Korea": "South Korea",
    "Russian Federation": "Russia",
    "US": "United States",
}

CENTCOM_COUNTRIES = (
    "Saudi Arabia",
    "United Arab Emirates",
    "Iraq",
    "Kuwait",
    "Qatar",
    "Oman",
    "Egypt",
    "Kazakhstan",
)

COUNTRY_TO_NODE = {
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

REGION_TO_NODE = {
    "AFRICOM": "AFRICOM",
    "CENTCOM": "CENTCOM",
    "CHINA": "CHINA",
    "EUCOM": "EUCOM",
    "INDOPACOM": "INDOPACOM",
    "IRAN": "IRAN",
    "NORTHCOM": "NORTHCOM",
    "RUSSIA": "RUSSIA",
    "SOUTHCOM": "SOUTHCOM",
}

SECTOR_VOLUME_WEIGHTS = {
    "heavy_logistics": {"gasoline": 0.10, "diesel": 0.32, "jet": 0.06},
    "aviation": {"gasoline": 0.02, "diesel": 0.01, "jet": 0.52},
    "agriculture": {"gasoline": 0.08, "diesel": 0.18, "jet": 0.02},
    "light_logistics": {"gasoline": 0.20, "diesel": 0.16, "jet": 0.03},
    "other": {"gasoline": 0.12, "diesel": 0.14, "jet": 0.18},
}

SECTOR_PRICE_PRIORITIES = {
    "heavy_logistics": {"gasoline": 0.84, "diesel": 1.32, "jet": 0.42},
    "aviation": {"gasoline": 0.20, "diesel": 0.24, "jet": 1.48},
    "agriculture": {"gasoline": 0.72, "diesel": 1.10, "jet": 0.18},
    "light_logistics": {"gasoline": 1.06, "diesel": 0.98, "jet": 0.20},
    "other": {"gasoline": 0.82, "diesel": 0.88, "jet": 0.58},
}

HOUSEHOLD_VOLUME_WEIGHTS = {
    "q1": {"gasoline": 0.07, "diesel": 0.01, "jet": 0.0},
    "q2": {"gasoline": 0.11, "diesel": 0.02, "jet": 0.0},
    "q3": {"gasoline": 0.14, "diesel": 0.03, "jet": 0.0},
    "q4": {"gasoline": 0.16, "diesel": 0.04, "jet": 0.0},
}

HOUSEHOLD_PRICE_PRIORITIES = {
    "q1": {"gasoline": 0.74, "diesel": 0.56, "jet": 0.0},
    "q2": {"gasoline": 0.86, "diesel": 0.66, "jet": 0.0},
    "q3": {"gasoline": 0.98, "diesel": 0.76, "jet": 0.0},
    "q4": {"gasoline": 1.16, "diesel": 0.92, "jet": 0.0},
}

# Public OUSD operational-energy data gives a roughly 73M bbl/year DoD fuel basis;
# DLA Energy public pages identify military jet and diesel fuels as core products.
PUBLIC_DOD_OPERATIONAL_FUEL_BBL_YEAR = 73_000_000.0
DOD_OVERSEAS_PURCHASE_SHARE = 0.48

MILITARY_BUYER_LOCALITY_WEIGHTS = {
    "NORTHCOM": 1.0 - DOD_OVERSEAS_PURCHASE_SHARE,
    "INDOPACOM": DOD_OVERSEAS_PURCHASE_SHARE,
}

MILITARY_OPERATIONAL_PRODUCT_MIX = {
    "gasoline": 0.00,
    "diesel": 0.35,
    "jet": 0.65,
}

MILITARY_PRICE_PRIORITIES = {
    "gasoline": 0.0,
    "diesel": 5.20,
    "jet": 5.80,
}

MILITARY_BUYER_NAMES = {
    "NORTHCOM": "NORTHCOM Military Fuel Buyer",
    "INDOPACOM": "INDOPACOM Military Fuel Buyer",
}

EXTRACTION_COST_BY_LOCALITY = {
    "AFRICOM": 43.0,
    "CENTCOM": 36.0,
    "CHINA": 52.0,
    "EUCOM": 50.0,
    "INDOPACOM": 48.0,
    "IRAN": 34.0,
    "NORTHCOM": 39.0,
    "RUSSIA": 39.0,
    "SOUTHCOM": 42.0,
}

STRUCTURAL_ROUTE_EMBARGOES = {
    ("IRAN", "EUCOM"),
    ("EUCOM", "IRAN"),
    ("IRAN", "NORTHCOM"),
    ("NORTHCOM", "IRAN"),
    ("RUSSIA", "EUCOM"),
    ("EUCOM", "RUSSIA"),
    ("RUSSIA", "NORTHCOM"),
    ("NORTHCOM", "RUSSIA"),
}

MODELED_PRODUCT_DEMAND_SHARE = 0.78
FALLBACK_PRODUCT_MIX = {
    "gasoline": 0.54,
    "diesel": 0.33,
    "jet": 0.13,
}


def _canonical_country(raw_country: str) -> str:
    stripped = (raw_country or "").strip()
    return COUNTRY_ALIASES.get(stripped, stripped)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_core_rows() -> dict[str, dict[str, str]]:
    return {row["locality"]: row for row in _read_csv_rows(CORE_DATA_PATH)}


def _load_country_series(path: Path, value_field: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for row in _read_csv_rows(path):
        country = _canonical_country(row["Country"].strip('"'))
        raw = (row[value_field] or "").replace(",", "")
        if not raw:
            continue
        try:
            values[country] = float(raw)
        except ValueError:
            continue
    return values


def _safe_share(part: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return part / total


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _thousand_bpd_to_bbl_week(value: float) -> float:
    return value * 1_000.0 * 7.0


def _weighted_average(pairs: list[tuple[float, float]], fallback: float) -> float:
    total_weight = sum(weight for weight, _ in pairs)
    if total_weight <= 0:
        return fallback
    return sum(weight * value for weight, value in pairs) / total_weight


def _solve_partner_value(combined: float, share: float, known_value: float) -> float:
    remaining_share = 1.0 - share
    if remaining_share <= 1e-6:
        return combined
    return (combined - share * known_value) / remaining_share


def _country_to_node(country: str, region: str) -> str:
    normalized_country = _canonical_country(country)
    if normalized_country in COUNTRY_TO_NODE:
        return COUNTRY_TO_NODE[normalized_country]
    return REGION_TO_NODE.get(region, "INDOPACOM")


def _product_mix(
    gasoline_throughput_thousand_bpd: float,
    diesel_throughput_thousand_bpd: float,
    jet_throughput_thousand_bpd: float,
) -> dict[str, float]:
    total = gasoline_throughput_thousand_bpd + diesel_throughput_thousand_bpd + jet_throughput_thousand_bpd
    if total <= 0:
        return dict(FALLBACK_PRODUCT_MIX)
    return {
        "gasoline": gasoline_throughput_thousand_bpd / total,
        "diesel": diesel_throughput_thousand_bpd / total,
        "jet": jet_throughput_thousand_bpd / total,
    }


def _refinery_node_capacity_profile() -> dict[str, dict[str, float]]:
    profile = {
        node_id: {
            "capacity_bpd": 0.0,
            "gasoline_bpd": 0.0,
            "diesel_bpd": 0.0,
            "jet_bpd": 0.0,
        }
        for node_id in NODE_IDS
    }
    for row in _read_csv_rows(REFINERY_AGENT_PATH):
        node_id = _country_to_node(row["assigned_country"], row["region"])
        profile[node_id]["capacity_bpd"] += float(row["total_peak_capacity_bpd"])
        profile[node_id]["gasoline_bpd"] += float(row["approx_gasoline_capacity_bpd"])
        profile[node_id]["diesel_bpd"] += float(row["approx_diesel_capacity_bpd"])
        profile[node_id]["jet_bpd"] += float(row["approx_jet_capacity_bpd"])
    return profile


def _build_locality_state(
    locality_id: str,
    *,
    gdp_per_capita: float,
    gini: float,
    oil_consumption_thousand_bpd: float,
    oil_production_thousand_bpd: float,
    refinery_capacity_thousand_bpd: float,
    refinery_throughput_thousand_bpd: float,
    gasoline_throughput_thousand_bpd: float,
    diesel_throughput_thousand_bpd: float,
    jet_throughput_thousand_bpd: float,
) -> LocalityState:
    product_mix = _product_mix(
        gasoline_throughput_thousand_bpd,
        diesel_throughput_thousand_bpd,
        jet_throughput_thousand_bpd,
    )
    modeled_products_total = _thousand_bpd_to_bbl_week(oil_consumption_thousand_bpd * MODELED_PRODUCT_DEMAND_SHARE)
    return LocalityState(
        id=locality_id,
        label=LOCALITY_LABELS[locality_id],
        gdp_per_capita=gdp_per_capita,
        gini=gini,
        baseline_crude_production_bbl_week=_thousand_bpd_to_bbl_week(oil_production_thousand_bpd),
        baseline_refinery_capacity_bbl_week=_thousand_bpd_to_bbl_week(refinery_capacity_thousand_bpd),
        baseline_refinery_throughput_bbl_week=_thousand_bpd_to_bbl_week(refinery_throughput_thousand_bpd),
        base_product_demand_bbl_week={
            product: modeled_products_total * product_mix[product]
            for product in PRODUCTS
        },
        fear_multiplier=1.0,
        position=LOCALITY_POSITIONS[locality_id],
    )


def load_localities() -> dict[str, LocalityState]:
    core = _read_core_rows()
    consumption_by_country = _load_country_series(OIL_CONSUMPTION_PATH, "Consumption_Thousand_Barrels_Daily_2024")
    production_by_country = _load_country_series(OIL_PRODUCTION_PATH, "Production_Thousand_Barrels_Daily_2024")
    refinery_profile = _refinery_node_capacity_profile()

    localities: dict[str, LocalityState] = {}

    direct_row_map = {
        "AFRICOM": "USAFRICOM",
        "EUCOM": "USEUCOM",
        "RUSSIA": "USEUCOM-CIS",
        "CHINA": "USINDOPACOM-CHINA",
        "INDOPACOM": "USINDOPACOM",
        "NORTHCOM": "USNORTHCOM",
    }
    for node_id, source_key in direct_row_map.items():
        row = core[source_key]
        localities[node_id] = _build_locality_state(
            node_id,
            gdp_per_capita=float(row["gdp_per_capita_usd_2024"]),
            gini=float(row["gini_coefficient_weighted_latest_wb"]),
            oil_consumption_thousand_bpd=float(row["oil_consumption_thousand_bpd_2024"]),
            oil_production_thousand_bpd=float(row["oil_production_thousand_bpd_2024"]),
            refinery_capacity_thousand_bpd=float(row["refinery_capacity_thousand_bpd_2024"]),
            refinery_throughput_thousand_bpd=float(row["refinery_throughput_thousand_bpd_2024"]),
            gasoline_throughput_thousand_bpd=float(row["gasoline_throughput_thousand_bpd_approx"]),
            diesel_throughput_thousand_bpd=float(row["diesel_throughput_thousand_bpd_approx"]),
            jet_throughput_thousand_bpd=float(row["jet_fuel_throughput_thousand_bpd_approx"]),
        )

    southcom_row = core["USSOUTHCOM"]
    venezuela_row = core["USSOUTHCOM-VENEZUELA"]
    southcom_consumption = float(southcom_row["oil_consumption_thousand_bpd_2024"])
    venezuela_consumption = float(venezuela_row["oil_consumption_thousand_bpd_2024"])
    localities["SOUTHCOM"] = _build_locality_state(
        "SOUTHCOM",
        gdp_per_capita=_weighted_average(
            [
                (southcom_consumption, float(southcom_row["gdp_per_capita_usd_2024"])),
                (venezuela_consumption, float(venezuela_row["gdp_per_capita_usd_2024"])),
            ],
            float(southcom_row["gdp_per_capita_usd_2024"]),
        ),
        gini=_weighted_average(
            [
                (southcom_consumption, float(southcom_row["gini_coefficient_weighted_latest_wb"])),
                (venezuela_consumption, float(venezuela_row["gini_coefficient_weighted_latest_wb"])),
            ],
            float(southcom_row["gini_coefficient_weighted_latest_wb"]),
        ),
        oil_consumption_thousand_bpd=southcom_consumption + venezuela_consumption,
        oil_production_thousand_bpd=float(southcom_row["oil_production_thousand_bpd_2024"]) + float(venezuela_row["oil_production_thousand_bpd_2024"]),
        refinery_capacity_thousand_bpd=float(southcom_row["refinery_capacity_thousand_bpd_2024"]) + float(venezuela_row["refinery_capacity_thousand_bpd_2024"]),
        refinery_throughput_thousand_bpd=float(southcom_row["refinery_throughput_thousand_bpd_2024"]) + float(venezuela_row["refinery_throughput_thousand_bpd_2024"]),
        gasoline_throughput_thousand_bpd=float(southcom_row["gasoline_throughput_thousand_bpd_approx"]) + float(venezuela_row["gasoline_throughput_thousand_bpd_approx"]),
        diesel_throughput_thousand_bpd=float(southcom_row["diesel_throughput_thousand_bpd_approx"]) + float(venezuela_row["diesel_throughput_thousand_bpd_approx"]),
        jet_throughput_thousand_bpd=float(southcom_row["jet_fuel_throughput_thousand_bpd_approx"]) + float(venezuela_row["jet_fuel_throughput_thousand_bpd_approx"]),
    )

    combined_row = core["USCENTCOM-IRAN"]
    combined_consumption = float(combined_row["oil_consumption_thousand_bpd_2024"])
    combined_production = float(combined_row["oil_production_thousand_bpd_2024"])
    combined_refinery_capacity = float(combined_row["refinery_capacity_thousand_bpd_2024"])
    combined_refinery_throughput = float(combined_row["refinery_throughput_thousand_bpd_2024"])
    combined_gasoline_throughput = float(combined_row["gasoline_throughput_thousand_bpd_approx"])
    combined_diesel_throughput = float(combined_row["diesel_throughput_thousand_bpd_approx"])
    combined_jet_throughput = float(combined_row["jet_fuel_throughput_thousand_bpd_approx"])
    combined_gdp = float(combined_row["gdp_per_capita_usd_2024"])
    combined_gini = float(combined_row["gini_coefficient_weighted_latest_wb"])

    iran_consumption_raw = consumption_by_country.get("Iran", 0.0)
    centcom_consumption_raw = sum(consumption_by_country.get(country, 0.0) for country in CENTCOM_COUNTRIES)
    iran_consumption_share = _safe_share(iran_consumption_raw, iran_consumption_raw + centcom_consumption_raw)

    iran_production_raw = production_by_country.get("Iran", 0.0)
    centcom_production_raw = sum(production_by_country.get(country, 0.0) for country in CENTCOM_COUNTRIES)
    iran_production_share = _safe_share(iran_production_raw, iran_production_raw + centcom_production_raw)

    iran_refinery_capacity_raw = refinery_profile["IRAN"]["capacity_bpd"]
    centcom_refinery_capacity_raw = refinery_profile["CENTCOM"]["capacity_bpd"]
    iran_refinery_capacity_share = _safe_share(
        iran_refinery_capacity_raw,
        iran_refinery_capacity_raw + centcom_refinery_capacity_raw,
    )

    iran_gdp = combined_gdp * 0.72
    centcom_gdp = _solve_partner_value(combined_gdp, iran_consumption_share, iran_gdp)
    iran_gini = min(50.0, combined_gini + 3.5)
    centcom_gini = _solve_partner_value(combined_gini, iran_consumption_share, iran_gini)

    localities["IRAN"] = _build_locality_state(
        "IRAN",
        gdp_per_capita=iran_gdp,
        gini=iran_gini,
        oil_consumption_thousand_bpd=combined_consumption * iran_consumption_share,
        oil_production_thousand_bpd=combined_production * iran_production_share,
        refinery_capacity_thousand_bpd=combined_refinery_capacity * iran_refinery_capacity_share,
        refinery_throughput_thousand_bpd=combined_refinery_throughput * iran_refinery_capacity_share,
        gasoline_throughput_thousand_bpd=combined_gasoline_throughput * iran_consumption_share,
        diesel_throughput_thousand_bpd=combined_diesel_throughput * iran_consumption_share,
        jet_throughput_thousand_bpd=combined_jet_throughput * iran_consumption_share,
    )
    localities["CENTCOM"] = _build_locality_state(
        "CENTCOM",
        gdp_per_capita=centcom_gdp,
        gini=centcom_gini,
        oil_consumption_thousand_bpd=combined_consumption * (1.0 - iran_consumption_share),
        oil_production_thousand_bpd=combined_production * (1.0 - iran_production_share),
        refinery_capacity_thousand_bpd=combined_refinery_capacity * (1.0 - iran_refinery_capacity_share),
        refinery_throughput_thousand_bpd=combined_refinery_throughput * (1.0 - iran_refinery_capacity_share),
        gasoline_throughput_thousand_bpd=combined_gasoline_throughput * (1.0 - iran_consumption_share),
        diesel_throughput_thousand_bpd=combined_diesel_throughput * (1.0 - iran_consumption_share),
        jet_throughput_thousand_bpd=combined_jet_throughput * (1.0 - iran_consumption_share),
    )

    return localities


def load_producers(localities: dict[str, LocalityState], path: Path = CRUDE_AGENT_PATH) -> list[CrudeProducerAgent]:
    rows = _read_csv_rows(path)
    producers: list[CrudeProducerAgent] = []
    grouped_supply: dict[str, float] = defaultdict(float)
    grouped_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        locality = _country_to_node(row["assigned_country"], row["region"])
        grouped_rows[locality].append(row)
        grouped_supply[locality] += float(row["weighted_crude_production_million_bbl_y"]) * 1_000_000.0 / 52.0

    for locality_id, locality_rows in grouped_rows.items():
        baseline_total = localities[locality_id].baseline_crude_production_bbl_week
        raw_total = max(1.0, grouped_supply[locality_id])
        scale = baseline_total / raw_total
        for row in locality_rows:
            country = _canonical_country(row["assigned_country"])
            producers.append(
                CrudeProducerAgent(
                    id=row["agent_country_key"],
                    name=row["representative_agent"],
                    country=country,
                    locality=locality_id,
                    baseline_supply_bbl_week=float(row["weighted_crude_production_million_bbl_y"]) * 1_000_000.0 / 52.0 * scale,
                    cost_floor_per_bbl=EXTRACTION_COST_BY_LOCALITY[locality_id],
                    risk_weight=0.22 if locality_id in {"IRAN", "RUSSIA"} else 0.12 if locality_id == "CENTCOM" else 0.08,
                )
            )
    return producers


def load_refiners(localities: dict[str, LocalityState], path: Path = REFINERY_AGENT_PATH) -> list[RefineryAgent]:
    rows = _read_csv_rows(path)
    grouped_capacity: dict[str, float] = defaultdict(float)
    grouped_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    refiners: list[RefineryAgent] = []

    for row in rows:
        locality = _country_to_node(row["assigned_country"], row["region"])
        grouped_rows[locality].append(row)
        grouped_capacity[locality] += float(row["total_peak_capacity_bpd"]) * 7.0

    for locality_id, locality_rows in grouped_rows.items():
        locality = localities[locality_id]
        baseline_utilization = locality.baseline_refinery_throughput_bbl_week / max(1.0, locality.baseline_refinery_capacity_bbl_week)
        baseline_utilization = max(0.45, min(0.97, baseline_utilization))
        raw_total = max(1.0, grouped_capacity[locality_id])
        scale = locality.baseline_refinery_capacity_bbl_week / raw_total
        for row in locality_rows:
            gasoline = float(row["approx_gasoline_capacity_bpd"])
            diesel = float(row["approx_diesel_capacity_bpd"])
            jet = float(row["approx_jet_capacity_bpd"])
            total_products = max(1.0, gasoline + diesel + jet)
            yield_shares = {
                "gasoline": gasoline / total_products,
                "diesel": diesel / total_products,
                "jet": jet / total_products,
            }
            complexity = float(row["approx_complexity_score"])
            refiners.append(
                RefineryAgent(
                    id=row["agent_country_key"],
                    name=row["representative_agent"],
                    country=_canonical_country(row["assigned_country"]),
                    locality=locality_id,
                    weekly_crude_capacity_bbl=float(row["total_peak_capacity_bpd"]) * 7.0 * scale,
                    baseline_utilization=baseline_utilization,
                    complexity_score=complexity,
                    processing_cost_per_bbl=8.0 + complexity * 0.55,
                    yield_shares=yield_shares,
                )
            )
    return refiners


def _income_multiplier(locality: LocalityState, quartile: str) -> float:
    wealth = max(0.65, min(1.45, locality.gdp_per_capita / 18000.0))
    inequality_penalty = max(0.82, min(1.20, 1.0 - (locality.gini - 35.0) / 200.0))
    quartile_boost = {"q1": 0.78, "q2": 0.92, "q3": 1.03, "q4": 1.16}[quartile]
    return wealth * inequality_penalty * quartile_boost


def _household_product_share(locality: LocalityState, product: str) -> float:
    wealth = _bounded(locality.gdp_per_capita / 20000.0, 0.45, 2.20)
    access_modifier = _bounded(1.0 - (locality.gini - 35.0) / 160.0, 0.80, 1.08)
    if product == "gasoline":
        return _bounded((0.18 + 0.11 * wealth) * access_modifier, 0.18, 0.42)
    if product == "diesel":
        return _bounded((0.02 + 0.03 * wealth) * access_modifier, 0.02, 0.09)
    return 0.0


def _household_quartile_weights(locality: LocalityState) -> dict[str, float]:
    inequality = _bounded((locality.gini - 35.0) / 18.0, -0.7, 1.0)
    weights = {
        "q1": 0.22 * (1.0 - 0.38 * inequality),
        "q2": 0.25 * (1.0 - 0.14 * inequality),
        "q3": 0.26 * (1.0 + 0.10 * inequality),
        "q4": 0.27 * (1.0 + 0.54 * inequality),
    }
    total = sum(max(0.01, value) for value in weights.values())
    return {quartile: max(0.01, value) / total for quartile, value in weights.items()}


def _military_buyer_base_demand(locality_id: str, sector_totals: dict[str, float]) -> dict[str, float]:
    buyer_weight = MILITARY_BUYER_LOCALITY_WEIGHTS.get(locality_id, 0.0)
    if buyer_weight <= 0.0:
        return {product: 0.0 for product in PRODUCTS}

    weekly_operational_fuel = PUBLIC_DOD_OPERATIONAL_FUEL_BBL_YEAR / 52.0
    buyer_total = weekly_operational_fuel * buyer_weight
    return {
        product: min(
            sector_totals[product],
            buyer_total * MILITARY_OPERATIONAL_PRODUCT_MIX[product],
        )
        for product in PRODUCTS
    }


def build_demand_agents(localities: dict[str, LocalityState]) -> list[DemandAgent]:
    agents: list[DemandAgent] = []
    for locality_id, locality in localities.items():
        quartile_weights = _household_quartile_weights(locality)
        household_totals = {
            product: locality.base_product_demand_bbl_week[product] * _household_product_share(locality, product)
            for product in PRODUCTS
        }
        sector_totals = {
            product: max(0.0, locality.base_product_demand_bbl_week[product] - household_totals[product])
            for product in PRODUCTS
        }
        military_totals = {product: 0.0 for product in PRODUCTS}
        if locality_id in MILITARY_BUYER_LOCALITY_WEIGHTS:
            military_totals = _military_buyer_base_demand(locality_id, sector_totals)
            sector_totals = {
                product: max(0.0, sector_totals[product] - military_totals[product])
                for product in PRODUCTS
            }

        sector_weight_totals = {
            product: sum(SECTOR_VOLUME_WEIGHTS[sector][product] for sector in SECTOR_VOLUME_WEIGHTS)
            for product in PRODUCTS
        }
        if sum(military_totals.values()) > 0.0:
            agents.append(
                DemandAgent(
                    id=f"{locality_id.lower()}-military-buyer",
                    name=MILITARY_BUYER_NAMES[locality_id],
                    locality=locality_id,
                    agent_kind="military",
                    segment="military",
                    base_demand_bbl_week=military_totals,
                    price_priority=dict(MILITARY_PRICE_PRIORITIES),
                    income_multiplier=1.0,
                )
            )

        for sector, weights in SECTOR_VOLUME_WEIGHTS.items():
            base_demand = {}
            for product in PRODUCTS:
                share = weights[product] / max(1e-6, sector_weight_totals[product])
                base_demand[product] = sector_totals[product] * share
            agents.append(
                DemandAgent(
                    id=f"{locality_id.lower()}-sector-{sector}",
                    name=f"{LOCALITY_LABELS[locality_id]} {sector.replace('_', ' ').title()}",
                    locality=locality_id,
                    agent_kind="sector",
                    segment=sector,
                    base_demand_bbl_week=base_demand,
                    price_priority=dict(SECTOR_PRICE_PRIORITIES[sector]),
                    income_multiplier=1.0,
                )
            )

        for quartile in HOUSEHOLD_QUARTILES:
            household_product_weight_totals = {
                product: sum(
                    quartile_weights[candidate] * HOUSEHOLD_VOLUME_WEIGHTS[candidate][product]
                    for candidate in HOUSEHOLD_QUARTILES
                )
                for product in PRODUCTS
            }
            base_demand = {
                product: household_totals[product]
                * quartile_weights[quartile]
                * HOUSEHOLD_VOLUME_WEIGHTS[quartile][product]
                / max(1e-6, household_product_weight_totals[product])
                for product in PRODUCTS
            }
            agents.append(
                DemandAgent(
                    id=f"{locality_id.lower()}-household-{quartile}",
                    name=f"{LOCALITY_LABELS[locality_id]} {quartile.upper()} Households",
                    locality=locality_id,
                    agent_kind="household",
                    segment=quartile,
                    base_demand_bbl_week=base_demand,
                    price_priority=dict(HOUSEHOLD_PRICE_PRIORITIES[quartile]),
                    income_multiplier=_income_multiplier(locality, quartile),
                )
            )
    return agents


def _apply_structural_route_policies(routes: dict[tuple[str, str], RouteState]) -> None:
    for key in STRUCTURAL_ROUTE_EMBARGOES:
        route = routes[key]
        route.blocked = True
        route.capacity_multiplier = 0.0
        route.base_capacity_bbl = 0.0
        route.shipping_cost_per_bbl = 0.0


def build_default_routes(localities: dict[str, LocalityState]) -> dict[tuple[str, str], RouteState]:
    routes: dict[tuple[str, str], RouteState] = {}
    for origin_id, origin in localities.items():
        for destination_id, destination in localities.items():
            if origin_id == destination_id:
                routes[(origin_id, destination_id)] = RouteState(
                    origin=origin_id,
                    destination=destination_id,
                    latency_weeks=0,
                    shipping_cost_per_bbl=0.45,
                    capacity_multiplier=1.0,
                    blocked=False,
                    base_capacity_bbl=max(origin.baseline_crude_production_bbl_week, destination.baseline_refinery_throughput_bbl_week) * 1.35,
                )
                continue
            dx = origin.position[0] - destination.position[0]
            dy = origin.position[1] - destination.position[1]
            distance = sqrt(dx * dx + dy * dy)
            if distance < 0.20:
                latency = 1
                cost = 2.8
            elif distance < 0.42:
                latency = 2
                cost = 5.2
            else:
                latency = 3
                cost = 7.8
            base_capacity = destination.baseline_refinery_throughput_bbl_week * (0.65 if distance < 0.30 else 0.38)
            base_capacity = max(base_capacity, 900_000.0)
            routes[(origin_id, destination_id)] = RouteState(
                origin=origin_id,
                destination=destination_id,
                latency_weeks=latency,
                shipping_cost_per_bbl=cost,
                capacity_multiplier=1.0,
                blocked=False,
                base_capacity_bbl=base_capacity,
            )
    _apply_structural_route_policies(routes)
    return routes


def get_scenario_presets() -> dict[str, ScenarioPreset]:
    gulf_exporters = ("CENTCOM", "IRAN")
    gulf_disruption_routes = {}
    for origin in gulf_exporters:
        for destination in NODE_IDS:
            if destination == origin:
                continue
            gulf_disruption_routes[(origin, destination)] = {
                "capacity_multiplier": 0.15,
                "shipping_cost_per_bbl": 16.5,
                "blocked": destination in {"EUCOM", "NORTHCOM", "INDOPACOM", "CHINA"},
            }

    return {
        "baseline": ScenarioPreset(
            name="Baseline",
            description="Reference case with steady demand, explicit geopolitical blocs, and Iranian export sanctions into EUCOM/NORTHCOM enforced by default.",
            operational_notes=(
                "Trigger: no new disruption beyond standing embargoes against Iranian, Russian, and Venezuelan barrels.",
                "Affected lanes/nodes: IRAN and RUSSIA have no route edge to EUCOM or NORTHCOM in either direction; Venezuelan crude is embargoed from EUCOM/NORTHCOM at the country layer.",
                "Market mechanism: the default 1.5x shipping environment raises landed costs while local inventories keep fear near steady state.",
            ),
        ),
        "hormuz_squeeze": ScenarioPreset(
            name="Hormuz Squeeze",
            description="A Gulf maritime squeeze hits both CENTCOM and IRAN outbound lanes, raising Asian landed costs and constraining global replacement barrels.",
            operational_notes=(
                "Trigger: Hormuz pressure constrains outbound Gulf cargoes from CENTCOM and IRAN.",
                "Affected lanes/nodes: CENTCOM and IRAN outbound exports to EUCOM, NORTHCOM, INDOPACOM, and CHINA are blocked; remaining outbound lanes operate at 15% capacity with elevated shipping costs.",
                "Supply/refinery shock: CENTCOM crude supply falls to 55%, IRAN supply falls to 45%, and regional refinery throughput is impaired.",
                "Market mechanism: same-week panic raises refiner MWTP, producer asks, and product bids before shortages fully materialize.",
            ),
            route_overrides=gulf_disruption_routes,
            locality_fear_shocks={
                "CENTCOM": 0.42,
                "IRAN": 0.55,
                "EUCOM": 0.30,
                "INDOPACOM": 0.44,
                "CHINA": 0.46,
                "NORTHCOM": 0.14,
            },
            producer_supply_shocks={"CENTCOM": 0.55, "IRAN": 0.45},
            refinery_capacity_shocks={"CENTCOM": 0.82, "IRAN": 0.72, "CHINA": 0.82, "INDOPACOM": 0.84},
            military_demand_shocks={"NORTHCOM": 0.08, "INDOPACOM": 0.22},
        ),
        "cis_disruption": ScenarioPreset(
            name="Russia Disruption",
            description="Russian output falls sharply and EU-adjacent markets scramble for replacement barrels",
            operational_notes=(
                "Trigger: Russian output shock reduces exportable barrels and refinery activity in the CIS-aligned node.",
                "Affected lanes/nodes: RUSSIA and EUCOM absorb the first panic impulse as European replacement barrels bid against global demand.",
                "Supply/refinery shock: Russian crude supply falls to 55% and Russian refinery capacity falls to 78%.",
                "Market mechanism: EUCOM bids up alternative feedstock while Russian local scarcity feeds higher asks into surviving routes.",
            ),
            locality_fear_shocks={"RUSSIA": 0.50, "EUCOM": 0.38},
            producer_supply_shocks={"RUSSIA": 0.55},
            refinery_capacity_shocks={"RUSSIA": 0.78},
            military_demand_shocks={"NORTHCOM": 0.04, "INDOPACOM": 0.04},
        ),
        "venezuela_outage": ScenarioPreset(
            name="Venezuela Outage",
            description="A Venezuelan outage hits SOUTHCOM supply without pretending all of SOUTHCOM is Venezuela.",
            operational_notes=(
                "Trigger: Venezuelan production and refining capacity suffer a concentrated outage inside SOUTHCOM.",
                "Affected lanes/nodes: SOUTHCOM takes the direct supply hit while NORTHCOM sees secondary replacement-barrel pressure.",
                "Supply/refinery shock: Venezuelan producer output falls to 20% and Venezuelan refinery capacity falls to 28%.",
                "Market mechanism: local shortages push SOUTHCOM fear higher and make imported replacement products clear at wider delivered-cost spreads.",
            ),
            locality_fear_shocks={"SOUTHCOM": 0.36, "NORTHCOM": 0.10},
            producer_country_shocks={"Venezuela": 0.20},
            refinery_country_shocks={"Venezuela": 0.28},
            military_demand_shocks={"NORTHCOM": 0.05},
        ),
        "coordinated_mitigation": ScenarioPreset(
            name="Coordinated Mitigation",
            description="A policy-forward response layer that adds reserve release and refinery support.",
            operational_notes=(
                "Trigger: commander-directed mitigation deploys reserves and subsidies without introducing a new physical outage.",
                "Affected lanes/nodes: reserve barrels are weighted toward NORTHCOM, EUCOM, and INDOPACOM; all routes receive a modest shipping relief factor.",
                "Policy shock: 650 kbd reserve release, 10% refinery subsidy, 12% military priority, and 0.95x scenario shipping modifier.",
                "Market mechanism: extra crude cover and refinery support reduce rejected bids and protect jet/diesel fulfillment for readiness.",
            ),
            policy_defaults=PolicyControls(
                reserve_release_kbd=650.0,
                refinery_subsidy_pct=0.10,
                military_priority_pct=0.12,
                shipping_cost_multiplier=0.95,
            ),
        ),
    }


def default_simulation_config(selected_scenario: str = "baseline") -> SimulationConfig:
    return SimulationConfig(selected_scenario=selected_scenario)


def _baseline_warm_start_config(config: SimulationConfig, warm_start_weeks: int) -> SimulationConfig:
    return SimulationConfig(
        seed=config.seed,
        start_week=config.start_week - warm_start_weeks,
        selected_scenario="baseline",
        route_overrides=dict(config.route_overrides),
        policy_controls=PolicyControls(
            shipping_cost_multiplier=config.policy_controls.shipping_cost_multiplier,
        ),
        demand_sensitivity=config.demand_sensitivity,
        inventory_cover_weeks=config.inventory_cover_weeks,
        warm_start_weeks=0,
    )


def _warm_start_baseline_equilibrium(world: WorldState, config: SimulationConfig) -> None:
    warm_start_weeks = max(0, int(config.warm_start_weeks))
    if warm_start_weeks <= 0:
        return

    display_week = config.start_week
    world.week = display_week - warm_start_weeks
    warm_config = _baseline_warm_start_config(config, warm_start_weeks)
    scenarios = get_scenario_presets()
    for _ in range(warm_start_weeks):
        step_world(world, warm_config, scenarios)

    settled_week = world.week
    for shipment in world.shipments_in_transit:
        remaining_weeks = max(1, shipment.arrival_week - settled_week)
        shipment.arrival_week = display_week + remaining_weeks

    for locality in world.localities.values():
        locality.fear_multiplier = max(0.97, min(1.03, locality.fear_multiplier))
        world.crude_inventory[locality.id] = max(
            world.crude_inventory[locality.id],
            locality.baseline_refinery_throughput_bbl_week * 0.95,
        )
        for product in PRODUCTS:
            world.product_inventory[locality.id][product] = max(
                world.product_inventory[locality.id][product],
                locality.base_product_demand_bbl_week[product] * 0.30,
            )
    for agent in world.demand_agents:
        for product in PRODUCTS:
            agent.backlog_bbl[product] = 0.0

    world.week = display_week
    world.history = []
    world.metrics = {}


def build_world(config: SimulationConfig | None = None) -> WorldState:
    config = config or SimulationConfig()
    localities = load_localities()
    producers = load_producers(localities)
    refiners = load_refiners(localities)
    demand_agents = build_demand_agents(localities)
    routes = build_default_routes(localities)

    crude_inventory = {
        locality_id: locality.baseline_refinery_throughput_bbl_week * 0.95
        for locality_id, locality in localities.items()
    }
    product_inventory = {
        locality_id: {product: locality.base_product_demand_bbl_week[product] * 0.18 for product in PRODUCTS}
        for locality_id, locality in localities.items()
    }
    product_cost_basis = {
        locality_id: {product: BASE_PRODUCT_PRICES[product] * 0.82 for product in PRODUCTS}
        for locality_id in localities
    }
    last_crude_prices = {
        locality_id: EXTRACTION_COST_BY_LOCALITY[locality_id] + 14.0
        for locality_id in localities
    }
    last_product_prices = {
        locality_id: {
            product: BASE_PRODUCT_PRICES[product] * (1.0 + (localities[locality_id].gdp_per_capita / 100000.0))
            for product in PRODUCTS
        }
        for locality_id in localities
    }

    world = WorldState(
        week=config.start_week,
        localities=localities,
        producers=producers,
        refiners=refiners,
        demand_agents=demand_agents,
        routes=routes,
        shipments_in_transit=[],
        crude_inventory=crude_inventory,
        product_inventory=product_inventory,
        product_cost_basis=product_cost_basis,
        strategic_reserve_inventory_bbl=DEFAULT_SPR_INVENTORY_BBL,
        strategic_reserve_capacity_bbl=SPR_STORAGE_CAPACITY_BBL,
        strategic_reserve_cash_usd=0.0,
        strategic_reserve_pending_returns=[],
        last_crude_price_by_locality=last_crude_prices,
        last_product_prices=last_product_prices,
    )
    _warm_start_baseline_equilibrium(world, config)
    return world
