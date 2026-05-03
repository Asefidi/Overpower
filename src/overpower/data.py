from __future__ import annotations

import csv
from collections import defaultdict
from math import sqrt
from pathlib import Path

from .sim import (
    BASE_PRODUCT_PRICES,
    PRODUCTS,
    CrudeProducerAgent,
    DemandAgent,
    LocalityState,
    PolicyControls,
    RefineryAgent,
    RouteState,
    ScenarioPreset,
    SimulationConfig,
    WorldState,
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

EXTRACTION_COST_BY_LOCALITY = {
    "AFRICOM": 43.0,
    "CENTCOM": 36.0,
    "CHINA": 52.0,
    "EUCOM": 50.0,
    "INDOPACOM": 48.0,
    "IRAN": 34.0,
    "NORTHCOM": 49.0,
    "RUSSIA": 39.0,
    "SOUTHCOM": 42.0,
}

SANCTIONED_EXPORT_BANS = {
    ("IRAN", "EUCOM"),
    ("IRAN", "NORTHCOM"),
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
    oil_production_thousand_bpd: float,
    refinery_capacity_thousand_bpd: float,
    refinery_throughput_thousand_bpd: float,
    gasoline_throughput_thousand_bpd: float,
    diesel_throughput_thousand_bpd: float,
    jet_throughput_thousand_bpd: float,
) -> LocalityState:
    return LocalityState(
        id=locality_id,
        label=LOCALITY_LABELS[locality_id],
        gdp_per_capita=gdp_per_capita,
        gini=gini,
        baseline_crude_production_bbl_week=_thousand_bpd_to_bbl_week(oil_production_thousand_bpd),
        baseline_refinery_capacity_bbl_week=_thousand_bpd_to_bbl_week(refinery_capacity_thousand_bpd),
        baseline_refinery_throughput_bbl_week=_thousand_bpd_to_bbl_week(refinery_throughput_thousand_bpd),
        base_product_demand_bbl_week={
            "gasoline": _thousand_bpd_to_bbl_week(gasoline_throughput_thousand_bpd),
            "diesel": _thousand_bpd_to_bbl_week(diesel_throughput_thousand_bpd),
            "jet": _thousand_bpd_to_bbl_week(jet_throughput_thousand_bpd),
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


def build_demand_agents(localities: dict[str, LocalityState]) -> list[DemandAgent]:
    agents: list[DemandAgent] = []
    for locality_id, locality in localities.items():
        demand_allocations: dict[str, list[tuple[str, str, dict[str, float], dict[str, float], float]]] = defaultdict(list)
        for sector, weights in SECTOR_VOLUME_WEIGHTS.items():
            demand_allocations["sector"].append((
                sector,
                sector,
                weights,
                SECTOR_PRICE_PRIORITIES[sector],
                1.0,
            ))
        for quartile, weights in HOUSEHOLD_VOLUME_WEIGHTS.items():
            demand_allocations["household"].append((
                quartile,
                quartile,
                weights,
                HOUSEHOLD_PRICE_PRIORITIES[quartile],
                _income_multiplier(locality, quartile),
            ))

        product_weight_totals = {
            product: sum(item[2][product] for entries in demand_allocations.values() for item in entries)
            for product in PRODUCTS
        }
        for agent_kind, entries in demand_allocations.items():
            for segment, label, volume_weights, price_priorities, income_multiplier in entries:
                base_demand = {}
                for product in PRODUCTS:
                    product_total = locality.base_product_demand_bbl_week[product] * 0.90
                    share = volume_weights[product] / max(1e-6, product_weight_totals[product])
                    base_demand[product] = product_total * share
                agents.append(
                    DemandAgent(
                        id=f"{locality_id.lower()}-{agent_kind}-{segment}",
                        name=f"{LOCALITY_LABELS[locality_id]} {label.replace('_', ' ').title()}",
                        locality=locality_id,
                        agent_kind=agent_kind,
                        segment=segment,
                        base_demand_bbl_week=base_demand,
                        price_priority=dict(price_priorities),
                        income_multiplier=income_multiplier,
                    )
                )
    return agents


def _apply_structural_route_policies(routes: dict[tuple[str, str], RouteState]) -> None:
    for key in SANCTIONED_EXPORT_BANS:
        route = routes[key]
        route.blocked = True
        route.capacity_multiplier = 0.0


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
        ),
        "hormuz_squeeze": ScenarioPreset(
            name="Hormuz Squeeze",
            description="A Gulf maritime squeeze hits both CENTCOM and IRAN outbound lanes, raising Asian landed costs and constraining global replacement barrels.",
            route_overrides=gulf_disruption_routes,
            locality_fear_shocks={
                "CENTCOM": 0.24,
                "IRAN": 0.30,
                "EUCOM": 0.14,
                "INDOPACOM": 0.18,
                "CHINA": 0.12,
            },
            producer_supply_shocks={"CENTCOM": 0.55, "IRAN": 0.45},
            refinery_capacity_shocks={"CENTCOM": 0.82, "IRAN": 0.72},
        ),
        "cis_disruption": ScenarioPreset(
            name="Russia Disruption",
            description="Russian output falls sharply and EU-adjacent markets scramble for replacement barrels without treating all of EUCOM as Russia.",
            locality_fear_shocks={"RUSSIA": 0.26, "EUCOM": 0.18},
            producer_supply_shocks={"RUSSIA": 0.55},
            refinery_capacity_shocks={"RUSSIA": 0.78},
        ),
        "venezuela_outage": ScenarioPreset(
            name="Venezuela Outage",
            description="A Venezuelan outage hits SOUTHCOM supply without pretending all of SOUTHCOM is Venezuela.",
            locality_fear_shocks={"SOUTHCOM": 0.16},
            producer_country_shocks={"Venezuela": 0.20},
            refinery_country_shocks={"Venezuela": 0.28},
        ),
        "coordinated_mitigation": ScenarioPreset(
            name="Coordinated Mitigation",
            description="A policy-forward response layer that adds reserve release and refinery support.",
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

    return WorldState(
        week=config.start_week,
        localities=localities,
        producers=producers,
        refiners=refiners,
        demand_agents=demand_agents,
        routes=routes,
        shipments_in_transit=[],
        crude_inventory=crude_inventory,
        product_inventory=product_inventory,
        last_crude_price_by_locality=last_crude_prices,
        last_product_prices=last_product_prices,
    )
