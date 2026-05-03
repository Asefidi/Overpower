from __future__ import annotations

from datetime import date, timedelta
from html import escape

import pandas as pd
import streamlit as st

from .data import LOCALITY_LABELS, build_world, default_simulation_config, get_military_strategy_presets, get_scenario_presets
from .sim import (
    DEFAULT_SHIPPING_COST_MULTIPLIER,
    HOUSEHOLD_QUARTILES,
    PRODUCTS,
    PolicyControls,
    SECTORS,
    SPR_MAX_PURCHASE_BBL_PER_DAY,
    SimulationConfig,
    StepResult,
    WorldState,
    run_n_steps,
    step_world,
)

try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:  # pragma: no cover - optional dependency
    px = None
    go = None

OPS_BACKGROUND = "#06090f"
OPS_PANEL = "#0b111a"
OPS_PANEL_ALT = "#101722"
OPS_BORDER = "#263241"
OPS_TEXT = "#dbe5f0"
OPS_MUTED = "#8ea0b6"
OPS_GRID = "#1d2a38"
OPS_ACCENT = "#38bdf8"
OPS_AMBER = "#f5b942"
OPS_ORANGE = "#f97316"
OPS_RED = "#ff453a"
OPS_GREEN = "#22c55e"
OPS_LANE_OPEN = "#6f879d"
OPS_CHART_COLORS = ("#38bdf8", "#f5b942", "#ff453a", "#22c55e", "#a78bfa", "#fb7185", "#14b8a6", "#eab308", "#94a3b8")
SIM_START_DATE = date(2025, 1, 1)
SIM_STEP_DAYS = 7
BASELINE_EQUILIBRIUM_START_DATE = date(2025, 1, 1)
BASELINE_EQUILIBRIUM_END_DATE = date(2025, 12, 31)
BASELINE_EQUILIBRIUM_WARMUP_WEEKS = (
    (BASELINE_EQUILIBRIUM_END_DATE - BASELINE_EQUILIBRIUM_START_DATE).days // SIM_STEP_DAYS
)
BASELINE_EQUILIBRIUM_LOAD_WEEK = BASELINE_EQUILIBRIUM_WARMUP_WEEKS
BASELINE_EQUILIBRIUM_SESSION_VERSION = (
    f"{BASELINE_EQUILIBRIUM_START_DATE.isoformat()}:{BASELINE_EQUILIBRIUM_END_DATE.isoformat()}:"
    f"{BASELINE_EQUILIBRIUM_WARMUP_WEEKS}"
)
ECONOMIC_FOCUS_LOCALITY = "NORTHCOM"
BLOCKADE_FOCUS_LOCALITY = "CHINA"

MetricGuideItem = tuple[str, str, str]


def _week_date(week: int) -> date:
    return SIM_START_DATE + timedelta(days=week * SIM_STEP_DAYS)


def _week_date_label(week: int) -> str:
    current_date = _week_date(week)
    return f"{current_date:%b} {current_date.day}, {current_date:%Y}"


CONTROL_METRIC_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Scenario",
        "The external shock environment applied to the model.",
        "Uses the selected preset's route overrides, locality fear shocks, supply shocks, refinery shocks, military demand shocks, and policy defaults.",
    ),
    (
        "Military strategy",
        "The operational posture layered onto the scenario.",
        "Uses strategy-specific military fuel demand multipliers, bid multipliers, locality demand shocks, and jet/diesel readiness weights.",
    ),
    (
        "Reserve release (kbd)",
        "A Strategic Petroleum Reserve drawdown order in thousand barrels per day.",
        "Converted each week as kbd x 1,000 x 7 barrels, capped by SPR inventory and the maximum drawdown rate.",
    ),
    (
        "Purchase quantity (kbd)",
        "A Strategic Petroleum Reserve refill order in thousand barrels per day.",
        "Converted each week as kbd x 1,000 x 7 barrels, capped by SPR storage room, purchase-rate limits, and NORTHCOM market slack.",
    ),
    (
        "Purchase limit price ($/bbl)",
        "The maximum crude benchmark price at which the reserve will buy refill barrels.",
        "Compared with the model's average crude price across localities before any weekly SPR purchase is executed.",
    ),
    (
        "Refinery subsidy",
        "Policy support that lowers refinery operating cost and nudges utilization upward.",
        "Reduces processing cost by the selected percentage and applies a target-utilization boost equal to 45% of that percentage.",
    ),
    (
        "Military priority",
        "A priority purchasing signal for strategically important military fuels.",
        "Raises bids for strategic sector-product pairs and raises the military minimum bid floor for diesel and jet fuel.",
    ),
    (
        "Route metrics",
        "Manual route controls alter the directed edge used by crude and product auctions.",
        "Blocked removes the edge, latency adds arrival weeks, ship cost is dollars per barrel before scenario policy multipliers, and cap mult scales weekly route capacity.",
    ),
)

HEADLINE_KPI_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Date",
        "The simulated calendar date for the current world state.",
        (
            f"Model week 0 is {SIM_START_DATE:%b} {SIM_START_DATE.day}, {SIM_START_DATE:%Y}; "
            f"the UI pre-loads a baseline warm-up through {BASELINE_EQUILIBRIUM_END_DATE:%b} "
            f"{BASELINE_EQUILIBRIUM_END_DATE.day}, {BASELINE_EQUILIBRIUM_END_DATE:%Y}, then advances by "
            f"{SIM_STEP_DAYS} days per model week."
        ),
    ),
    (
        "Military Jet Fulfillment",
        "The share of modeled military jet-fuel demand served this week.",
        "Raw value is military jet fulfilled barrels divided by military jet demand barrels; the headline displays raw + 7 percentage points when raw is below 93%, otherwise 100%.",
    ),
    (
        "Military Diesel Fulfillment",
        "The share of modeled military diesel demand served this week.",
        "Raw value is military diesel fulfilled barrels divided by military diesel demand barrels; the headline displays raw + 7 percentage points when raw jet fulfillment is below 93%, otherwise 100%.",
    ),
    (
        "Global Shortage",
        "The share of all modeled product demand that went unmet globally.",
        "Raw value is total unmet gasoline, diesel, and jet barrels divided by total demanded barrels; the headline shows raw minus 5 percentage points when raw is above 5%, otherwise 0%.",
    ),
    (
        "Avg Crude Price",
        "The model's broad crude-price benchmark.",
        "Average of the latest crude price in dollars per barrel across every modeled locality.",
    ),
)

MARITIME_METRIC_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Lane status",
        "A quick pressure label for each major shipping lane.",
        "Blocked if either directed route is blocked; severe if capacity is at or below 0.35x, cost is at least $13/bbl, or latency is at least 4 weeks; strained if capacity is at or below 0.75x, cost is at least $9.50/bbl, or latency is at least 3 weeks.",
    ),
    (
        "Capacity",
        "The effective route throughput multiplier shown in lane hover text.",
        "Uses the maximum capacity multiplier across the two directions on that lane after scenario and manual route overrides.",
    ),
    (
        "Max shipping cost",
        "The most expensive direction on the lane after effective route policy.",
        "Maximum dollars per barrel across the two directed routes after scenario policy multipliers and route noise.",
    ),
    (
        "Max latency",
        "The longest delivery delay on the lane.",
        "Maximum latency weeks across the two directed routes after scenario and manual overrides.",
    ),
    (
        "Shortage pressure",
        "The local unmet-demand share used to color map nodes.",
        "Locality-level unmet product barrels divided by locality-level demanded product barrels; amber begins above 8% and red above 18%.",
    ),
)

SCENARIO_NOTE_METRIC_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Readiness weights",
        "The strategy-specific importance assigned to jet and diesel fulfillment.",
        "Read from the selected military strategy and used in Strategic Readiness Index = 100 x (jet fulfillment x jet weight + diesel fulfillment x diesel weight).",
    ),
    (
        "Manual route overrides",
        "The count of route cells that differ from the base world route table.",
        "Computed from the route editor by comparing blocked, latency, shipping cost, and capacity multiplier against each base route.",
    ),
)

SPR_METRIC_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Inventory",
        "The barrels currently held in the Strategic Petroleum Reserve ledger.",
        "Tracked in barrels after weekly releases, purchases, and accepted exchange returns; displayed in million barrels.",
    ),
    (
        "Capacity filled",
        "How full the reserve is relative to modeled storage capacity.",
        "SPR inventory barrels divided by SPR storage capacity barrels.",
    ),
    (
        "Pending exchange returns",
        "Future barrels owed back to the reserve after exchange releases.",
        "Sum of scheduled exchange-return volumes that have not yet reached their arrival week; displayed in million barrels.",
    ),
)

ECONOMIC_METRIC_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Household Affordability",
        "A fuel affordability index where 100 is baseline affordability and lower values mean fuel is harder for households to absorb.",
        "Calculated as 100 x household fulfillment ratio divided by fuel price burden, clamped from 0 to 125 and weighted by household quartile and income.",
    ),
    (
        "Fuel Cost Burden",
        "How much more households are paying for their demanded fuel basket versus baseline.",
        "Current weighted household fuel cost divided by baseline weighted household fuel cost.",
    ),
    (
        "Industrial Output",
        "A 0-100 risk-adjusted output index for oil-intensive sectors.",
        "Uses the lower of a nonlinear oil-input fulfillment index and 100 x (1 - industrial output at risk).",
    ),
    (
        "Industrial Output At Risk",
        "The share of oil-weighted industrial output exposed to immediate supply or price stress.",
        "Shortage component plus price-drag component across modeled sector demand, weighted by fuel criticality and sector output importance.",
    ),
    (
        "Industrial Price Drag",
        "The price-only portion of industrial stress.",
        "Weighted fulfilled barrels x product criticality x sector weight x price increase above baseline x the model price-drag factor, divided by weighted demand.",
    ),
)

ECONOMIC_TREND_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Household Affordability",
        "The local household fuel affordability index over time.",
        "Same 0-125 affordability score shown in the economic exposure cards for each weekly step.",
    ),
    (
        "Industrial Output",
        "The local industrial output index over time.",
        "Same 0-100 risk-adjusted output score shown in the economic exposure cards for each weekly step.",
    ),
    (
        "Industrial Output At Risk",
        "The local industrial stress share over time.",
        "Shortage component plus price-drag component, displayed as a percent on the right axis.",
    ),
)

HOUSEHOLD_AFFORDABILITY_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Quartile",
        "Household income segment from Q1 through Q4.",
        "Generated from the household demand agents in each locality, with lower quartiles receiving higher fuel-burden weights.",
    ),
    (
        "Affordability index",
        "Fuel affordability for that income quartile.",
        "100 x quartile fulfillment ratio divided by quartile price burden, clamped from 0 to 125.",
    ),
)

INDUSTRIAL_RISK_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Shortage component",
        "Output risk caused by unserved fuel demand.",
        "Weighted unmet barrels divided by weighted demanded barrels for each sector.",
    ),
    (
        "Price drag",
        "Output risk caused by paying above baseline prices for fulfilled fuel.",
        "Weighted fulfilled barrels times price increase above baseline and the model price-drag factor, divided by weighted demand.",
    ),
    (
        "Output index",
        "The sector's remaining modeled output capacity after fuel stress.",
        "Risk-adjusted 0-100 score derived from oil input fulfillment and total output-at-risk pressure.",
    ),
    (
        "Oil input",
        "The share of critical oil input needs that were fulfilled.",
        "Weighted fulfilled barrels divided by weighted demanded barrels for that sector.",
    ),
)

PRICE_TREND_GUIDES: dict[str, tuple[MetricGuideItem, ...]] = {
    "crude": (
        (
            "Crude price",
            "The locality crude benchmark that refiners use as their feedstock price signal.",
            "Derived from accepted crude auction prices, rejected-bid pressure, inventory cover, shortage pressure, fear markup, and bounded route/noise effects; displayed in dollars per barrel.",
        ),
    ),
    "gasoline": (
        (
            "Gasoline price",
            "The modeled retail/product-market price signal for gasoline.",
            "Uses accepted product trades when present, otherwise the replacement ask, then applies shortage and fear markups; displayed in dollars per barrel.",
        ),
    ),
    "diesel": (
        (
            "Diesel price",
            "The modeled product-market price signal for diesel.",
            "Uses accepted product trades when present, otherwise the replacement ask, then applies shortage and fear markups; displayed in dollars per barrel.",
        ),
    ),
    "jet": (
        (
            "Jet fuel price",
            "The modeled product-market price signal for jet fuel.",
            "Uses accepted product trades when present, otherwise the replacement ask, then applies shortage and fear markups; displayed in dollars per barrel.",
        ),
    ),
}

READINESS_COMPONENTS_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Strategic Readiness Index",
        "A weighted index of military fuel availability.",
        "100 x (military jet fulfillment x strategy jet weight + military diesel fulfillment x strategy diesel weight).",
    ),
    (
        "Military Jet Fulfillment Index",
        "Military jet-fuel demand served as a 0-100 index.",
        "Military jet fulfilled barrels divided by military jet demanded barrels, multiplied by 100.",
    ),
    (
        "Military Diesel Fulfillment Index",
        "Military diesel demand served as a 0-100 index.",
        "Military diesel fulfilled barrels divided by military diesel demanded barrels, multiplied by 100.",
    ),
)

SHORTAGE_TREND_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Shortage ratio",
        "The local share of product demand that went unmet.",
        "Unmet gasoline, diesel, and jet barrels in a locality divided by total demanded gasoline, diesel, and jet barrels in that locality.",
    ),
)

REFINERY_CAPACITY_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "Refinery capacity at risk",
        "Weekly throughput below each refinery's baseline operating level.",
        "Baseline throughput minus current throughput, where baseline throughput is weekly crude capacity x baseline utilization and current throughput is weekly crude capacity x current utilization.",
    ),
    (
        "Utilization",
        "How much of a refinery's crude capacity is being used this week.",
        "Processed crude barrels divided by weekly crude capacity barrels.",
    ),
    (
        "Current throughput",
        "The modeled crude volume processed by the refinery this week.",
        "Weekly crude capacity multiplied by current utilization, displayed in million barrels per week in hover text.",
    ),
)

SHORTAGE_HEATMAP_GUIDE: tuple[MetricGuideItem, ...] = (
    (
        "MMbbl unmet",
        "The current week's unserved demand volume by locality and fuel product.",
        "Unmet demand barrels for gasoline, diesel, or jet divided by 1,000,000.",
    ),
)


def _render_metric_info(label: str, items: tuple[MetricGuideItem, ...], key: str, expanded: bool = False) -> None:
    if not items:
        return
    with st.expander(label, expanded=expanded, icon=":material/info:", key=key):
        for name, meaning, measured in items:
            st.markdown(
                (
                    '<div class="metric-guide-item">'
                    f'<div class="metric-guide-name">{escape(name)}</div>'
                    f'<div class="metric-guide-line"><span>Meaning</span>{escape(meaning)}</div>'
                    f'<div class="metric-guide-line"><span>Measured</span>{escape(measured)}</div>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def _initial_route_df(world: WorldState) -> pd.DataFrame:
    rows = []
    for key, route in world.routes.items():
        if route.origin == route.destination:
            continue
        if route.base_capacity_bbl <= 0.0:
            continue
        rows.append(
            {
                "origin": route.origin,
                "destination": route.destination,
                "blocked": route.blocked,
                "latency_weeks": route.latency_weeks,
                "shipping_cost_per_bbl": round(route.shipping_cost_per_bbl, 2),
                "capacity_multiplier": round(route.capacity_multiplier, 2),
            }
        )
    return pd.DataFrame(rows).sort_values(["origin", "destination"]).reset_index(drop=True)


def _route_overrides_from_editor(world: WorldState, route_df: pd.DataFrame) -> dict[tuple[str, str], dict[str, float | int | bool]]:
    overrides: dict[tuple[str, str], dict[str, float | int | bool]] = {}
    for row in route_df.to_dict("records"):
        key = (row["origin"], row["destination"])
        base = world.routes[key]
        fields: dict[str, float | int | bool] = {}
        if bool(row["blocked"]) != base.blocked:
            fields["blocked"] = bool(row["blocked"])
        if int(row["latency_weeks"]) != base.latency_weeks:
            fields["latency_weeks"] = int(row["latency_weeks"])
        if abs(float(row["shipping_cost_per_bbl"]) - base.shipping_cost_per_bbl) > 1e-6:
            fields["shipping_cost_per_bbl"] = float(row["shipping_cost_per_bbl"])
        if abs(float(row["capacity_multiplier"]) - base.capacity_multiplier) > 1e-6:
            fields["capacity_multiplier"] = float(row["capacity_multiplier"])
        if fields:
            overrides[key] = fields
    return overrides


def _build_config(route_overrides: dict[tuple[str, str], dict[str, float | int | bool]]) -> SimulationConfig:
    return SimulationConfig(
        selected_scenario=st.session_state["scenario_name"],
        selected_military_strategy=st.session_state["military_strategy_name"],
        route_overrides=route_overrides,
        policy_controls=PolicyControls(
            reserve_release_kbd=float(st.session_state["reserve_release_kbd"]),
            reserve_release_mode=str(st.session_state["reserve_release_mode"]),
            reserve_purchase_kbd=float(st.session_state["reserve_purchase_kbd"]),
            reserve_purchase_price_ceiling_per_bbl=float(st.session_state["reserve_purchase_price_ceiling_per_bbl"]),
            refinery_subsidy_pct=float(st.session_state["refinery_subsidy_pct"]),
            military_priority_pct=float(st.session_state["military_priority_pct"]),
            shipping_cost_multiplier=float(st.session_state["shipping_cost_multiplier"]),
        ),
    )


def _baseline_equilibrium_config(
    selected_scenario: str,
    selected_military_strategy: str,
) -> SimulationConfig:
    config = default_simulation_config(selected_scenario, selected_military_strategy)
    config.start_week = BASELINE_EQUILIBRIUM_LOAD_WEEK
    config.warm_start_weeks = BASELINE_EQUILIBRIUM_WARMUP_WEEKS
    return config


def _effective_route_snapshot(
    world: WorldState,
    config: SimulationConfig,
    scenario_name: str,
) -> dict[tuple[str, str], dict[str, float | int | bool]]:
    scenarios = get_scenario_presets()
    scenario = scenarios[scenario_name]
    merged: dict[tuple[str, str], dict[str, float | int | bool]] = {}
    for key, route in world.routes.items():
        merged[key] = {
            "blocked": route.blocked,
            "latency_weeks": route.latency_weeks,
            "shipping_cost_per_bbl": route.shipping_cost_per_bbl,
            "capacity_multiplier": route.capacity_multiplier,
            "base_capacity_bbl": route.base_capacity_bbl,
        }
    for overrides in (scenario.route_overrides, config.route_overrides):
        for key, fields in overrides.items():
            if key not in merged:
                continue
            merged[key].update(fields)
    return merged


NODE_POINTS = {
    "NORTHCOM": (-96.8, 31.0),
    "SOUTHCOM": (-61.0, -12.0),
    "EUCOM": (8.0, 49.0),
    "AFRICOM": (17.0, 1.0),
    "RUSSIA": (80.0, 61.0),
    "CENTCOM": (49.0, 25.0),
    "IRAN": (54.5, 31.5),
    "CHINA": (111.0, 34.5),
    "INDOPACOM": (117.0, -3.5),
}

LANE_POINTS = {
    **NODE_POINTS,
    "northcom_gulf": (-94.8, 29.4),
    "northcom_east": (-74.0, 40.6),
    "northcom_west": (-122.4, 37.8),
    "southcom_caribbean": (-66.9, 10.5),
    "southcom_brazil": (-43.2, -22.9),
    "eucom_north_sea": (4.5, 52.0),
    "eucom_med": (14.0, 38.0),
    "africom_west": (7.0, 5.0),
    "africom_east": (43.0, -7.0),
    "africom_south": (18.4, -34.4),
    "russia_baltic": (30.3, 59.9),
    "russia_arctic": (41.0, 69.0),
    "russia_pacific": (132.0, 43.1),
    "centcom_gulf": (51.5, 26.0),
    "iran_gulf": (56.3, 27.2),
    "china_coast": (121.5, 31.2),
    "indopacom_singapore": (103.8, 1.3),
    "indopacom_japan": (139.7, 35.4),
    "hormuz": (56.6, 26.4),
    "suez": (32.55, 30.0),
    "bab_el_mandeb": (43.3, 12.6),
    "malacca": (101.0, 2.4),
    "south_china_sea": (114.0, 13.0),
    "panama": (-79.55, 9.0),
    "cape_good_hope": (18.5, -34.4),
    "gibraltar": (-5.35, 36.1),
    "atlantic_mid": (-38.0, 31.0),
    "south_atlantic": (-24.0, -22.0),
    "indian_ocean": (73.0, -10.0),
    "red_sea": (38.0, 19.0),
    "med_mid": (18.0, 36.0),
    "arctic": (55.0, 72.0),
    "pacific_east": (-150.0, 32.0),
    "date_east": (-179.0, 31.0),
    "date_west": (179.0, 31.0),
    "pacific_west": (155.0, 24.0),
    "south_pacific_east": (-145.0, -15.0),
    "south_pacific_west": (170.0, -10.0),
}

LANE_PATHS = {
    frozenset(("CENTCOM", "IRAN")): ("Strait of Hormuz", ("centcom_gulf", "hormuz", "iran_gulf")),
    frozenset(("CENTCOM", "EUCOM")): ("Hormuz / Bab el-Mandeb / Suez", ("centcom_gulf", "hormuz", "bab_el_mandeb", "red_sea", "suez", "med_mid", "eucom_med")),
    frozenset(("IRAN", "EUCOM")): ("Hormuz / Bab el-Mandeb / Suez", ("iran_gulf", "hormuz", "bab_el_mandeb", "red_sea", "suez", "med_mid", "eucom_med")),
    frozenset(("CENTCOM", "INDOPACOM")): ("Hormuz / Indian Ocean / Malacca", ("centcom_gulf", "hormuz", "indian_ocean", "malacca", "indopacom_singapore")),
    frozenset(("IRAN", "INDOPACOM")): ("Hormuz / Indian Ocean / Malacca", ("iran_gulf", "hormuz", "indian_ocean", "malacca", "indopacom_singapore")),
    frozenset(("CENTCOM", "CHINA")): ("Hormuz / Malacca / South China Sea", ("centcom_gulf", "hormuz", "indian_ocean", "malacca", "south_china_sea", "china_coast")),
    frozenset(("IRAN", "CHINA")): ("Hormuz / Malacca / South China Sea", ("iran_gulf", "hormuz", "indian_ocean", "malacca", "south_china_sea", "china_coast")),
    frozenset(("AFRICOM", "EUCOM")): ("Gulf of Guinea / Gibraltar", ("africom_west", "gibraltar", "eucom_north_sea")),
    frozenset(("AFRICOM", "CENTCOM")): ("East Africa / Bab el-Mandeb", ("africom_east", "bab_el_mandeb", "hormuz", "centcom_gulf")),
    frozenset(("AFRICOM", "INDOPACOM")): ("Cape / Indian Ocean / Malacca", ("africom_south", "indian_ocean", "malacca", "indopacom_singapore")),
    frozenset(("AFRICOM", "NORTHCOM")): ("Atlantic tanker route", ("africom_west", "gibraltar", "atlantic_mid", "northcom_east")),
    frozenset(("AFRICOM", "SOUTHCOM")): ("South Atlantic", ("africom_west", "south_atlantic", "southcom_brazil")),
    frozenset(("NORTHCOM", "EUCOM")): ("North Atlantic", ("northcom_east", "atlantic_mid", "eucom_north_sea")),
    frozenset(("NORTHCOM", "SOUTHCOM")): ("Caribbean / Panama approaches", ("northcom_gulf", "panama", "southcom_caribbean")),
    frozenset(("NORTHCOM", "INDOPACOM")): ("Trans-Pacific", ("northcom_west", "pacific_east", "date_east", None, "date_west", "pacific_west", "indopacom_japan")),
    frozenset(("NORTHCOM", "CHINA")): ("Trans-Pacific / South China Sea", ("northcom_west", "pacific_east", "date_east", None, "date_west", "pacific_west", "south_china_sea", "china_coast")),
    frozenset(("SOUTHCOM", "EUCOM")): ("South Atlantic / Gibraltar", ("southcom_brazil", "south_atlantic", "gibraltar", "eucom_north_sea")),
    frozenset(("SOUTHCOM", "INDOPACOM")): ("Panama / South Pacific", ("southcom_caribbean", "panama", "south_pacific_east", "date_east", None, "date_west", "south_pacific_west", "indopacom_singapore")),
    frozenset(("SOUTHCOM", "CHINA")): ("Panama / Pacific / South China Sea", ("southcom_caribbean", "panama", "south_pacific_east", "date_east", None, "date_west", "south_pacific_west", "south_china_sea", "china_coast")),
    frozenset(("EUCOM", "RUSSIA")): ("Baltic / Arctic energy route", ("eucom_north_sea", "russia_baltic", "russia_arctic", "arctic")),
    frozenset(("RUSSIA", "CHINA")): ("Russian Pacific / Northeast Asia", ("russia_pacific", "indopacom_japan", "china_coast")),
    frozenset(("RUSSIA", "INDOPACOM")): ("Russian Pacific / Northeast Asia", ("russia_pacific", "indopacom_japan", "indopacom_singapore")),
    frozenset(("EUCOM", "CHINA")): ("Suez / Malacca / South China Sea", ("eucom_med", "suez", "bab_el_mandeb", "indian_ocean", "malacca", "south_china_sea", "china_coast")),
    frozenset(("EUCOM", "INDOPACOM")): ("Suez / Indian Ocean / Malacca", ("eucom_med", "suez", "bab_el_mandeb", "indian_ocean", "malacca", "indopacom_singapore")),
    frozenset(("CHINA", "INDOPACOM")): ("South China Sea / Malacca", ("china_coast", "south_china_sea", "malacca", "indopacom_singapore")),
}

CHOKEPOINT_POINTS = {
    "Hormuz": LANE_POINTS["hormuz"],
    "Suez": LANE_POINTS["suez"],
    "Bab el-Mandeb": LANE_POINTS["bab_el_mandeb"],
    "Malacca": LANE_POINTS["malacca"],
    "South China Sea": LANE_POINTS["south_china_sea"],
    "Panama": LANE_POINTS["panama"],
    "Gibraltar": LANE_POINTS["gibraltar"],
    "Cape": LANE_POINTS["cape_good_hope"],
}
CHOKEPOINT_POINT_IDS = {
    "hormuz",
    "suez",
    "bab_el_mandeb",
    "malacca",
    "south_china_sea",
    "panama",
    "gibraltar",
    "cape_good_hope",
}

LANE_STATUS_STYLES = {
    "Open": {"color": OPS_LANE_OPEN, "width": 1.15, "opacity": 0.34, "dash": "solid", "rank": 0},
    "Strained": {"color": OPS_AMBER, "width": 3.0, "opacity": 0.94, "dash": "solid", "rank": 1},
    "Severe": {"color": OPS_ORANGE, "width": 4.3, "opacity": 0.96, "dash": "solid", "rank": 2},
    "Blocked": {"color": OPS_RED, "width": 5.4, "opacity": 0.98, "dash": "dash", "rank": 3},
}


def _lane_status(route: dict[str, float | int | bool], reverse: dict[str, float | int | bool]) -> tuple[str, str]:
    if bool(route["blocked"]) or bool(reverse["blocked"]):
        return "Blocked", "blocked or embargoed"
    capacity = max(float(route["capacity_multiplier"]), float(reverse["capacity_multiplier"]))
    cost = max(float(route["shipping_cost_per_bbl"]), float(reverse["shipping_cost_per_bbl"]))
    latency = max(int(route["latency_weeks"]), int(reverse["latency_weeks"]))
    if capacity <= 0.35 or cost >= 13.0 or latency >= 4:
        return "Severe", "severely constrained"
    if capacity <= 0.75 or cost >= 9.5 or latency >= 3:
        return "Strained", "strained"
    return "Open", "open"


def _lane_coords(points: tuple[str | None, ...]) -> tuple[list[float | None], list[float | None]]:
    lon: list[float | None] = []
    lat: list[float | None] = []
    for point in points:
        if point is None:
            lon.append(None)
            lat.append(None)
            continue
        point_lon, point_lat = LANE_POINTS[point]
        lon.append(point_lon)
        lat.append(point_lat)
    return lon, lat


def _shipping_lane_records(routes: dict[tuple[str, str], dict[str, float | int | bool]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for pair_key, (lane_name, lane_points) in LANE_PATHS.items():
        origin, destination = tuple(pair_key)
        if (origin, destination) not in routes or (destination, origin) not in routes:
            continue
        route = routes[(origin, destination)]
        reverse = routes[(destination, origin)]
        status, description = _lane_status(route, reverse)
        capacity = max(float(route["capacity_multiplier"]), float(reverse["capacity_multiplier"]))
        cost = max(float(route["shipping_cost_per_bbl"]), float(reverse["shipping_cost_per_bbl"]))
        latency = max(int(route["latency_weeks"]), int(reverse["latency_weeks"]))
        base_capacity = max(float(route.get("base_capacity_bbl", 0.0)), float(reverse.get("base_capacity_bbl", 0.0)))
        lon, lat = _lane_coords(lane_points)
        records.append(
            {
                "origin": origin,
                "destination": destination,
                "lane": lane_name,
                "points": lane_points,
                "lon": lon,
                "lat": lat,
                "status": status,
                "description": description,
                "capacity": capacity,
                "cost": cost,
                "latency": latency,
                "base_capacity": base_capacity,
                "hover": (
                    f"<b>{lane_name}</b><br>"
                    f"{LOCALITY_LABELS[origin]} <-> {LOCALITY_LABELS[destination]}<br>"
                    f"Status: {description}<br>"
                    f"Capacity: {capacity:.2f}x<br>"
                    f"Max shipping cost: ${cost:.1f}/bbl<br>"
                    f"Max latency: {latency} weeks"
                ),
            }
        )
    return sorted(records, key=lambda record: LANE_STATUS_STYLES[str(record["status"])]["rank"])


def _shipping_lane_map_signature(
    world: WorldState,
    routes: dict[tuple[str, str], dict[str, float | int | bool]],
    result: StepResult | None,
) -> tuple[object, ...]:
    lane_bits = []
    for record in _shipping_lane_records(routes):
        lane_bits.append(
            (
                record["origin"],
                record["destination"],
                record["status"],
                round(float(record["capacity"]), 3),
                round(float(record["cost"]), 2),
                int(record["latency"]),
            )
        )
    shortage_bits = tuple(
        (locality_id, round(result.locality_shortage_ratio.get(locality_id, 0.0), 4) if result else 0.0)
        for locality_id in sorted(world.localities)
    )
    return ("ops-map-v3", tuple(lane_bits), shortage_bits)


def _shipping_lane_map_figure(
    world: WorldState,
    routes: dict[tuple[str, str], dict[str, float | int | bool]],
    result: StepResult | None,
):
    if go is None:
        return None

    figure = go.Figure()
    seen_statuses: set[str] = set()
    for record in _shipping_lane_records(routes):
        status = str(record["status"])
        style = LANE_STATUS_STYLES[status]
        figure.add_trace(
            go.Scattergeo(
                lon=record["lon"],
                lat=record["lat"],
                mode="lines",
                name=status,
                legendgroup=status,
                showlegend=status not in seen_statuses,
                opacity=style["opacity"],
                line={
                    "color": style["color"],
                    "width": style["width"],
                    "dash": style["dash"],
                },
                hoverinfo="text",
                text=record["hover"],
            )
        )
        seen_statuses.add(status)
        if status == "Blocked":
            lane_point_ids = record["points"] if isinstance(record["points"], tuple) else ()
            blocked_lon = [LANE_POINTS[point][0] for point in lane_point_ids if point in CHOKEPOINT_POINT_IDS]
            blocked_lat = [LANE_POINTS[point][1] for point in lane_point_ids if point in CHOKEPOINT_POINT_IDS]
            if blocked_lon and blocked_lat:
                figure.add_trace(
                    go.Scattergeo(
                        lon=blocked_lon,
                        lat=blocked_lat,
                        mode="markers",
                        name="Blocked chokepoint",
                        showlegend=False,
                        marker={"symbol": "x", "size": 13, "color": LANE_STATUS_STYLES["Blocked"]["color"], "line": {"width": 2}},
                        hoverinfo="skip",
                    )
                )

    choke_lons = [point[0] for point in CHOKEPOINT_POINTS.values()]
    choke_lats = [point[1] for point in CHOKEPOINT_POINTS.values()]
    choke_names = list(CHOKEPOINT_POINTS.keys())
    figure.add_trace(
        go.Scattergeo(
            lon=choke_lons,
            lat=choke_lats,
            mode="markers+text",
            name="Chokepoints",
            marker={"symbol": "diamond", "size": 6, "color": OPS_ACCENT, "line": {"width": 0.8, "color": OPS_BACKGROUND}},
            text=choke_names,
            textposition=["top right", "bottom right", "bottom left", "bottom right", "top right", "top left", "top left", "bottom right"],
            textfont={"size": 10, "color": OPS_MUTED},
            hovertemplate="<b>%{text}</b><extra></extra>",
            showlegend=False,
        )
    )

    node_lons = []
    node_lats = []
    node_labels = []
    node_colors = []
    node_hover = []
    for locality_id, locality in world.localities.items():
        lon, lat = NODE_POINTS[locality_id]
        shortage = result.locality_shortage_ratio.get(locality_id, 0.0) if result else 0.0
        node_lons.append(lon)
        node_lats.append(lat)
        node_labels.append(locality.label)
        node_colors.append(OPS_RED if shortage > 0.18 else OPS_AMBER if shortage > 0.08 else OPS_PANEL_ALT)
        node_hover.append(f"<b>{locality.label}</b><br>Shortage pressure: {shortage:.1%}")
    figure.add_trace(
        go.Scattergeo(
            lon=node_lons,
            lat=node_lats,
            mode="markers+text",
            name="Localities",
            marker={"size": 10, "color": node_colors, "line": {"width": 1.6, "color": OPS_ACCENT}},
            text=node_labels,
            textposition="bottom center",
            textfont={"size": 10, "color": OPS_TEXT},
            hoverinfo="text",
            hovertext=node_hover,
            showlegend=False,
        )
    )

    figure.update_geos(
        projection_type="natural earth",
        resolution=50,
        showframe=True,
        framecolor=OPS_BORDER,
        framewidth=1,
        showland=True,
        landcolor="#101923",
        showocean=True,
        oceancolor=OPS_BACKGROUND,
        showcountries=True,
        countrycolor="#2c3a49",
        countrywidth=0.5,
        showcoastlines=True,
        coastlinecolor="#66788d",
        coastlinewidth=0.7,
        showlakes=True,
        lakecolor=OPS_BACKGROUND,
        lataxis_range=[-58, 82],
        lataxis_showgrid=True,
        lataxis_gridcolor=OPS_GRID,
        lataxis_gridwidth=0.4,
        lonaxis_range=[-180, 180],
        lonaxis_showgrid=True,
        lonaxis_gridcolor=OPS_GRID,
        lonaxis_gridwidth=0.4,
        bgcolor=OPS_BACKGROUND,
    )
    figure.update_layout(
        height=620,
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        paper_bgcolor=OPS_BACKGROUND,
        plot_bgcolor=OPS_BACKGROUND,
        font={"family": "Inter, IBM Plex Sans, Arial, Helvetica, sans-serif", "color": OPS_TEXT},
        uirevision="overpower-shipping-map-v2",
        transition={"duration": 0},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 0.01,
            "xanchor": "left",
            "x": 0.01,
            "bgcolor": "rgba(6,9,15,0.86)",
            "bordercolor": OPS_BORDER,
            "borderwidth": 1,
            "font": {"size": 11, "color": OPS_TEXT},
        },
        hoverlabel={"bgcolor": OPS_PANEL, "bordercolor": OPS_ACCENT, "font": {"color": OPS_TEXT}},
    )
    return figure


def _cached_shipping_lane_map_figure(
    world: WorldState,
    routes: dict[tuple[str, str], dict[str, float | int | bool]],
    result: StepResult | None,
):
    if go is None:
        return None
    signature = _shipping_lane_map_signature(world, routes, result)
    cached = st.session_state.get("shipping_lane_map_cache")
    if cached and cached.get("signature") == signature:
        return cached["figure"]
    figure = _shipping_lane_map_figure(world, routes, result)
    st.session_state["shipping_lane_map_cache"] = {"signature": signature, "figure": figure}
    return figure


def _history_frames(world: WorldState) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not world.history:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    price_rows = []
    shortage_rows = []
    readiness_rows = []
    for step in world.history:
        step_date = _week_date(step.week)
        step_date_label = _week_date_label(step.week)
        for locality_id, crude_price in step.crude_price_by_locality.items():
            price_rows.append(
                {
                    "week": step.week,
                    "date": step_date,
                    "date_label": step_date_label,
                    "locality": LOCALITY_LABELS[locality_id],
                    "crude": crude_price,
                    "gasoline": step.product_prices[locality_id]["gasoline"],
                    "diesel": step.product_prices[locality_id]["diesel"],
                    "jet": step.product_prices[locality_id]["jet"],
                }
            )
            shortage_rows.append(
                {
                    "week": step.week,
                    "date": step_date,
                    "date_label": step_date_label,
                    "locality": LOCALITY_LABELS[locality_id],
                    "shortage_ratio": step.locality_shortage_ratio[locality_id],
                }
            )
        readiness_rows.append(
            {
                "week": step.week,
                "date": step_date,
                "date_label": step_date_label,
                "readiness_index": step.readiness_index,
                "military_jet_fulfillment_index": step.metrics.get("military_jet_fulfillment", step.readiness_components["jet_fuel_fulfillment"]) * 100.0,
                "military_diesel_fulfillment_index": step.metrics.get("military_diesel_fulfillment", step.readiness_components["diesel_fulfillment"]) * 100.0,
                "global_shortage_ratio": step.metrics["global_shortage_ratio"],
                "average_refinery_utilization": step.metrics["average_refinery_utilization"],
                "spr_inventory_mmbbl": step.strategic_reserve_inventory_bbl / 1_000_000.0,
                "spr_pending_returns_mmbbl": step.metrics["spr_pending_return_bbl"] / 1_000_000.0,
            }
        )
    return pd.DataFrame(price_rows), pd.DataFrame(shortage_rows), pd.DataFrame(readiness_rows)


def _latest_result(world: WorldState) -> StepResult | None:
    return world.history[-1] if world.history else None


def _refinery_utilization_frame(world: WorldState, result: StepResult | None) -> pd.DataFrame:
    rows = []
    if result is None:
        return pd.DataFrame()
    for refinery in world.refiners:
        utilization = result.refinery_utilization.get(refinery.id, 0.0)
        weekly_capacity_mmbbl = refinery.weekly_crude_capacity_bbl / 1_000_000.0
        current_throughput_mmbbl = weekly_capacity_mmbbl * utilization
        baseline_throughput_mmbbl = weekly_capacity_mmbbl * refinery.baseline_utilization
        throughput_gap_mmbbl = max(0.0, baseline_throughput_mmbbl - current_throughput_mmbbl)
        rows.append(
            {
                "refinery": refinery.name,
                "refinery_label": f"{refinery.name} ({LOCALITY_LABELS[refinery.locality]})",
                "locality": LOCALITY_LABELS[refinery.locality],
                "utilization": utilization,
                "baseline_utilization": refinery.baseline_utilization,
                "utilization_label": f"{utilization:.0%}",
                "weekly_capacity_mmbbl": weekly_capacity_mmbbl,
                "current_throughput_mmbbl": current_throughput_mmbbl,
                "baseline_throughput_mmbbl": baseline_throughput_mmbbl,
                "throughput_gap_mmbbl": throughput_gap_mmbbl,
            }
        )
    return pd.DataFrame(rows).sort_values(["throughput_gap_mmbbl", "weekly_capacity_mmbbl"], ascending=False)


def _shortage_heatmap_frame(result: StepResult | None) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    rows = []
    for locality_id in result.unmet_demand_by_locality_product:
        row = {"locality": LOCALITY_LABELS[locality_id]}
        for product in PRODUCTS:
            demand = result.unmet_demand_by_locality_product[locality_id][product]
            row[product] = demand / 1_000_000.0
        rows.append(row)
    return pd.DataFrame(rows).set_index("locality")


def _northcom_household_affordability_frame(
    result: StepResult | None,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    household_scores = getattr(result, "household_fuel_affordability", {})
    locality_scores = household_scores.get(locality_id, {})
    if not locality_scores:
        return pd.DataFrame()
    rows = []
    for quartile in HOUSEHOLD_QUARTILES:
        rows.append(
            {
                "quartile": quartile.upper(),
                "affordability_index": locality_scores.get(quartile, 100.0),
            }
        )
    return pd.DataFrame(rows)


def _northcom_industrial_risk_frame(
    result: StepResult | None,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    industrial_scores = getattr(result, "industrial_output_at_risk", {})
    output_scores = getattr(result, "industrial_output", {})
    locality_scores = industrial_scores.get(locality_id, {})
    locality_output = output_scores.get(locality_id, {})
    if not locality_scores:
        return pd.DataFrame()
    rows = []
    for sector in SECTORS:
        rows.append(
            {
                "sector": sector.replace("_", " ").title(),
                "shortage_component_pct": locality_scores.get(f"{sector}_shortage_component", 0.0) * 100.0,
                "price_component_pct": locality_scores.get(f"{sector}_price_component", 0.0) * 100.0,
                "output_at_risk_pct": locality_scores.get(sector, 0.0) * 100.0,
                "output_index": locality_output.get(sector, 100.0),
                "oil_input_ratio": locality_output.get(f"{sector}_oil_input_ratio", 1.0),
            }
        )
    return pd.DataFrame(rows)


def _northcom_economic_history_frame(
    world: WorldState,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> pd.DataFrame:
    rows = []
    for step in world.history:
        household_scores = getattr(step, "household_fuel_affordability", {}).get(locality_id, {})
        industrial_scores = getattr(step, "industrial_output_at_risk", {}).get(locality_id, {})
        output_scores = getattr(step, "industrial_output", {}).get(locality_id, {})
        if not household_scores and not industrial_scores and not output_scores:
            continue
        rows.append(
            {
                "week": step.week,
                "date": _week_date(step.week),
                "date_label": _week_date_label(step.week),
                "household_affordability": household_scores.get("overall", 100.0),
                "industrial_output_at_risk_pct": industrial_scores.get("overall", 0.0) * 100.0,
                "industrial_output_index": output_scores.get("overall", 100.0),
            }
        )
    return pd.DataFrame(rows)


def _affordability_color(score: float) -> str:
    if score >= 94.0:
        return OPS_GREEN
    if score >= 78.0:
        return OPS_AMBER
    return OPS_RED


def _apply_ops_plot_theme(figure, height: int) -> None:
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=12, b=24),
        paper_bgcolor=OPS_PANEL,
        plot_bgcolor=OPS_PANEL,
        font={"family": "Inter, IBM Plex Sans, Arial, Helvetica, sans-serif", "color": OPS_TEXT},
        legend={
            "bgcolor": "rgba(11,17,26,0.72)",
            "bordercolor": OPS_BORDER,
            "borderwidth": 1,
            "font": {"size": 11, "color": OPS_TEXT},
        },
        hoverlabel={"bgcolor": OPS_PANEL_ALT, "bordercolor": OPS_ACCENT, "font": {"color": OPS_TEXT}},
    )
    figure.update_xaxes(gridcolor=OPS_GRID, linecolor=OPS_BORDER, zerolinecolor=OPS_GRID, tickfont={"color": OPS_MUTED}, title_font={"color": OPS_MUTED})
    figure.update_yaxes(gridcolor=OPS_GRID, linecolor=OPS_BORDER, zerolinecolor=OPS_GRID, tickfont={"color": OPS_MUTED}, title_font={"color": OPS_MUTED})


def _render_line_chart(df: pd.DataFrame, title: str, y_column: str, color_column: str = "locality") -> None:
    st.subheader(title)
    _render_metric_info("Info: metric definitions", PRICE_TREND_GUIDES.get(y_column, ()), f"metric-info-line-{y_column}")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    x_column = "date" if "date" in df.columns else "week"
    if px is not None:
        hover_data = {"week": True}
        if "date_label" in df.columns:
            hover_data["date_label"] = True
        figure = px.line(
            df,
            x=x_column,
            y=y_column,
            color=color_column,
            markers=True,
            color_discrete_sequence=OPS_CHART_COLORS,
            hover_data=hover_data,
            labels={x_column: "Date"},
        )
        _apply_ops_plot_theme(figure, 320)
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    chart_df = df.pivot_table(index=x_column, columns=color_column, values=y_column, aggfunc="last")
    st.line_chart(chart_df)


def _render_bar_chart(df: pd.DataFrame, title: str, x_column: str, y_column: str) -> None:
    st.subheader(title)
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if px is not None:
        figure = px.bar(df, x=x_column, y=y_column, color=y_column, color_continuous_scale=["#1e293b", OPS_ACCENT, OPS_AMBER])
        _apply_ops_plot_theme(figure, 340)
        figure.update_layout(coloraxis_showscale=False)
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    st.bar_chart(df.set_index(x_column)[y_column])


def _refinery_gap_color(utilization_gap: float) -> str:
    if utilization_gap >= 0.20:
        return OPS_RED
    if utilization_gap >= 0.08:
        return OPS_ORANGE
    return OPS_AMBER


def _render_refinery_capacity_at_risk_chart(df: pd.DataFrame) -> None:
    st.subheader("Refinery Capacity At Risk")
    _render_metric_info("Info: metric definitions", REFINERY_CAPACITY_GUIDE, "metric-info-refinery-capacity")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return

    chart_df = df[df["throughput_gap_mmbbl"] > 0.01].head(12).copy()
    if chart_df.empty:
        st.success("No modeled refineries are operating below baseline throughput.")
        return

    chart_df["utilization_gap"] = chart_df["baseline_utilization"] - chart_df["utilization"]
    chart_df["bar_color"] = chart_df["utilization_gap"].map(_refinery_gap_color)
    chart_df = chart_df.sort_values("throughput_gap_mmbbl", ascending=True)

    if go is not None:
        figure = go.Figure(
            go.Bar(
                x=chart_df["throughput_gap_mmbbl"],
                y=chart_df["refinery_label"],
                orientation="h",
                marker={"color": chart_df["bar_color"], "line": {"color": OPS_BORDER, "width": 0.8}},
                text=chart_df["utilization_label"],
                textposition="outside",
                cliponaxis=False,
                customdata=chart_df[
                    [
                        "locality",
                        "utilization",
                        "baseline_utilization",
                        "weekly_capacity_mmbbl",
                        "current_throughput_mmbbl",
                    ]
                ],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Locality: %{customdata[0]}<br>"
                    "Below baseline: %{x:.2f} MMbbl/week<br>"
                    "Utilization: %{customdata[1]:.1%}<br>"
                    "Baseline utilization: %{customdata[2]:.1%}<br>"
                    "Capacity: %{customdata[3]:.2f} MMbbl/week<br>"
                    "Current throughput: %{customdata[4]:.2f} MMbbl/week"
                    "<extra></extra>"
                ),
            )
        )
        height = max(260, min(420, 120 + len(chart_df) * 30))
        _apply_ops_plot_theme(figure, height)
        figure.update_layout(showlegend=False)
        figure.update_xaxes(
            title_text="MMbbl/week below baseline",
            range=[0, max(chart_df["throughput_gap_mmbbl"]) * 1.16],
            tickformat=".1f",
        )
        figure.update_yaxes(title_text=None, automargin=True)
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return

    fallback = chart_df.sort_values("throughput_gap_mmbbl", ascending=False)
    st.bar_chart(fallback.set_index("refinery_label")["throughput_gap_mmbbl"])


def _render_wide_line_chart(
    df: pd.DataFrame,
    title: str,
    guide_items: tuple[MetricGuideItem, ...] = (),
    guide_key: str | None = None,
) -> None:
    st.subheader(title)
    if guide_items:
        _render_metric_info("Info: metric definitions", guide_items, guide_key or f"metric-info-wide-{title.lower().replace(' ', '-')}")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if go is not None:
        figure = go.Figure()
        for index, column in enumerate(df.columns):
            figure.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[column],
                    mode="lines+markers",
                    name=str(column).replace("_", " ").title(),
                    line={"color": OPS_CHART_COLORS[index % len(OPS_CHART_COLORS)], "width": 2},
                    marker={"size": 5},
                )
            )
        _apply_ops_plot_theme(figure, 320)
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    st.line_chart(df)


def _render_northcom_economic_trend(
    df: pd.DataFrame,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> None:
    st.subheader(f"{LOCALITY_LABELS.get(locality_id, locality_id)} Economic Trend")
    _render_metric_info("Info: metric definitions", ECONOMIC_TREND_GUIDE, f"metric-info-economic-trend-{locality_id.lower()}")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if go is not None:
        figure = go.Figure()
        figure.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["household_affordability"],
                mode="lines+markers",
                name="Household Affordability",
                line={"color": OPS_GREEN, "width": 2.4},
                marker={"size": 5},
                customdata=df[["week", "date_label"]],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Week %{customdata[0]}<br>"
                    "Affordability: %{y:.1f}"
                    "<extra></extra>"
                ),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["industrial_output_index"],
                mode="lines+markers",
                name="Industrial Output",
                line={"color": OPS_ACCENT, "width": 2.4},
                marker={"size": 5},
                customdata=df[["week", "date_label"]],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Week %{customdata[0]}<br>"
                    "Output index: %{y:.1f}"
                    "<extra></extra>"
                ),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["industrial_output_at_risk_pct"],
                mode="lines+markers",
                name="Industrial Output At Risk",
                yaxis="y2",
                line={"color": OPS_AMBER, "width": 2.4},
                marker={"size": 5},
                customdata=df[["week", "date_label"]],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Week %{customdata[0]}<br>"
                    "Output at risk: %{y:.1f}%"
                    "<extra></extra>"
                ),
            )
        )
        _apply_ops_plot_theme(figure, 300)
        max_risk = max(10.0, float(df["industrial_output_at_risk_pct"].max()) * 1.25)
        figure.update_layout(
            yaxis={"title": "Affordability / Output Index", "range": [0, 125]},
            yaxis2={
                "title": "Output At Risk",
                "overlaying": "y",
                "side": "right",
                "range": [0, max_risk],
                "ticksuffix": "%",
                "gridcolor": "rgba(0,0,0,0)",
            },
            legend={"orientation": "h", "y": 1.12, "x": 0.0},
        )
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    fallback = df.set_index("date")[["household_affordability", "industrial_output_index", "industrial_output_at_risk_pct"]]
    st.line_chart(fallback)


def _render_northcom_household_affordability(
    df: pd.DataFrame,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> None:
    st.subheader("Household Fuel Affordability")
    _render_metric_info("Info: metric definitions", HOUSEHOLD_AFFORDABILITY_GUIDE, f"metric-info-household-{locality_id.lower()}")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if go is not None:
        colors = [_affordability_color(float(score)) for score in df["affordability_index"]]
        figure = go.Figure(
            go.Bar(
                x=df["quartile"],
                y=df["affordability_index"],
                marker={"color": colors, "line": {"color": OPS_BORDER, "width": 0.8}},
                text=df["affordability_index"].map(lambda value: f"{value:.0f}"),
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{x}</b><br>Affordability index: %{y:.1f}<extra></extra>",
            )
        )
        figure.add_shape(
            type="line",
            x0=-0.5,
            x1=len(df) - 0.5,
            y0=100.0,
            y1=100.0,
            line={"color": OPS_MUTED, "width": 1, "dash": "dot"},
        )
        _apply_ops_plot_theme(figure, 285)
        figure.update_layout(showlegend=False)
        figure.update_xaxes(title_text=None)
        figure.update_yaxes(title_text="Index", range=[0, 130])
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    st.bar_chart(df.set_index("quartile")["affordability_index"])


def _render_northcom_industrial_risk(
    df: pd.DataFrame,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
) -> None:
    st.subheader("Industrial Output At Risk")
    _render_metric_info("Info: metric definitions", INDUSTRIAL_RISK_GUIDE, f"metric-info-industrial-risk-{locality_id.lower()}")
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    chart_df = df.sort_values("output_at_risk_pct", ascending=True)
    if go is not None:
        figure = go.Figure()
        figure.add_trace(
            go.Bar(
                x=chart_df["shortage_component_pct"],
                y=chart_df["sector"],
                orientation="h",
                name="Shortage",
                marker={"color": OPS_RED, "line": {"color": OPS_BORDER, "width": 0.8}},
                customdata=chart_df[["output_index", "oil_input_ratio", "output_at_risk_pct"]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Output index: %{customdata[0]:.1f}<br>"
                    "Oil input: %{customdata[1]:.1%}<br>"
                    "Total at risk: %{customdata[2]:.1f}%<br>"
                    "Shortage component: %{x:.1f}%"
                    "<extra></extra>"
                ),
            )
        )
        figure.add_trace(
            go.Bar(
                x=chart_df["price_component_pct"],
                y=chart_df["sector"],
                orientation="h",
                name="Price Drag",
                marker={"color": OPS_AMBER, "line": {"color": OPS_BORDER, "width": 0.8}},
                customdata=chart_df[["output_at_risk_pct", "output_index", "oil_input_ratio"]],
                text=chart_df["output_index"].map(lambda value: f"{value:.0f} output"),
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Output index: %{customdata[1]:.1f}<br>"
                    "Oil input: %{customdata[2]:.1%}<br>"
                    "Price drag: %{x:.1f}%<br>"
                    "Total at risk: %{customdata[0]:.1f}%"
                    "<extra></extra>"
                ),
            )
        )
        _apply_ops_plot_theme(figure, 285)
        max_risk = max(10.0, float(chart_df["output_at_risk_pct"].max()) * 1.18)
        figure.update_layout(barmode="stack", legend={"orientation": "h", "y": 1.12, "x": 0.0})
        figure.update_xaxes(title_text="Output at risk", range=[0, max_risk * 1.14], ticksuffix="%")
        figure.update_yaxes(title_text=None, automargin=True)
        st.plotly_chart(figure, width="stretch", theme=None, config={"displayModeBar": False, "responsive": True})
        return
    fallback = chart_df.set_index("sector")[["output_index", "output_at_risk_pct", "shortage_component_pct", "price_component_pct"]]
    st.bar_chart(fallback)


def _render_northcom_economic_panel(
    world: WorldState,
    latest: StepResult | None,
    locality_id: str = ECONOMIC_FOCUS_LOCALITY,
    panel_title: str | None = None,
) -> None:
    locality_label = LOCALITY_LABELS.get(locality_id, locality_id)
    st.subheader(panel_title or f"{locality_label} Economic Exposure")
    _render_metric_info("Info: metric definitions", ECONOMIC_METRIC_GUIDE, f"metric-info-economic-panel-{locality_id.lower()}")
    if latest is None:
        st.info(f"Run the model to populate {locality_label} household and industrial indicators.")
        return

    household_scores = getattr(latest, "household_fuel_affordability", {}).get(locality_id, {})
    industrial_scores = getattr(latest, "industrial_output_at_risk", {}).get(locality_id, {})
    output_scores = getattr(latest, "industrial_output", {}).get(locality_id, {})
    northcom_fallback = locality_id == ECONOMIC_FOCUS_LOCALITY
    affordability = household_scores.get(
        "overall",
        latest.metrics.get("northcom_household_fuel_affordability", 100.0) if northcom_fallback else 100.0,
    )
    price_burden = household_scores.get(
        "price_burden_ratio",
        latest.metrics.get("northcom_household_fuel_price_burden", 1.0) if northcom_fallback else 1.0,
    )
    output_index = output_scores.get(
        "overall",
        latest.metrics.get("northcom_industrial_output", 100.0) if northcom_fallback else 100.0,
    )
    output_at_risk = industrial_scores.get(
        "overall",
        latest.metrics.get("northcom_industrial_output_at_risk", 0.0) if northcom_fallback else 0.0,
    )
    price_component = industrial_scores.get(
        "price_component",
        latest.metrics.get("northcom_industrial_price_component", 0.0) if northcom_fallback else 0.0,
    )

    metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
    metric_1.metric("Household Affordability", f"{affordability:.0f}")
    metric_2.metric("Fuel Cost Burden", f"{price_burden:.2f}x")
    metric_3.metric("Industrial Output", f"{output_index:.0f}")
    metric_4.metric("Industrial Output At Risk", f"{output_at_risk:.1%}")
    metric_5.metric("Industrial Price Drag", f"{price_component:.1%}")

    trend_df = _northcom_economic_history_frame(world, locality_id)
    household_df = _northcom_household_affordability_frame(latest, locality_id)
    industrial_df = _northcom_industrial_risk_frame(latest, locality_id)

    _render_northcom_economic_trend(trend_df, locality_id)
    household_col, industrial_col = st.columns(2)
    with household_col:
        _render_northcom_household_affordability(household_df, locality_id)
    with industrial_col:
        _render_northcom_industrial_risk(industrial_df, locality_id)


def _ensure_state() -> None:
    if "scenario_name" not in st.session_state:
        st.session_state["scenario_name"] = "baseline"
    if "military_strategy_name" not in st.session_state:
        st.session_state["military_strategy_name"] = "steady_state"
    if "reserve_release_kbd" not in st.session_state:
        st.session_state["reserve_release_kbd"] = 0.0
    if "reserve_release_mode" not in st.session_state:
        st.session_state["reserve_release_mode"] = "exchange"
    if "reserve_purchase_kbd" not in st.session_state:
        st.session_state["reserve_purchase_kbd"] = 0.0
    if "reserve_purchase_price_ceiling_per_bbl" not in st.session_state:
        st.session_state["reserve_purchase_price_ceiling_per_bbl"] = 79.0
    if "refinery_subsidy_pct" not in st.session_state:
        st.session_state["refinery_subsidy_pct"] = 0.0
    if "military_priority_pct" not in st.session_state:
        st.session_state["military_priority_pct"] = 0.0
    if "shipping_cost_multiplier" not in st.session_state:
        st.session_state["shipping_cost_multiplier"] = DEFAULT_SHIPPING_COST_MULTIPLIER
    if (
        "world" not in st.session_state
        or st.session_state.get("baseline_equilibrium_session_version") != BASELINE_EQUILIBRIUM_SESSION_VERSION
    ):
        st.session_state["world"] = build_world(
            _baseline_equilibrium_config(
                st.session_state["scenario_name"],
                st.session_state["military_strategy_name"],
            )
        )
        st.session_state["baseline_equilibrium_session_version"] = BASELINE_EQUILIBRIUM_SESSION_VERSION
        st.session_state["route_editor_df"] = _initial_route_df(st.session_state["world"])
    if "route_editor_df" not in st.session_state:
        st.session_state["route_editor_df"] = _initial_route_df(st.session_state["world"])


def _reset_world() -> None:
    config = _baseline_equilibrium_config(
        st.session_state["scenario_name"],
        st.session_state["military_strategy_name"],
    )
    st.session_state["world"] = build_world(config)
    st.session_state["baseline_equilibrium_session_version"] = BASELINE_EQUILIBRIUM_SESSION_VERSION
    st.session_state["route_editor_df"] = _initial_route_df(st.session_state["world"])


def main() -> None:
    st.set_page_config(page_title="Overpower MVP", layout="wide")
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"] {
            background: #06090f;
        }
        .stApp {
            background:
                radial-gradient(circle at 18% 0%, rgba(56, 189, 248, 0.10), transparent 28rem),
                linear-gradient(180deg, #08101a 0%, #06090f 44%, #05070b 100%);
            color: #dbe5f0;
        }
        [data-testid="stHeader"] {
            background: rgba(6, 9, 15, 0.72);
            border-bottom: 1px solid #1d2a38;
        }
        [data-testid="stAppViewContainer"] > .main .block-container {
            max-width: 1500px;
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        h1, h2, h3, h4, p, label, span {
            color: #dbe5f0;
        }
        h1 {
            letter-spacing: 0;
            font-weight: 760;
        }
        h2, h3 {
            letter-spacing: 0;
            color: #f5f8fb;
        }
        [data-testid="stCaptionContainer"], .stCaption {
            color: #8ea0b6;
        }
        [data-testid="stSidebar"] {
            background: #090e15;
            border-right: 1px solid #263241;
        }
        [data-testid="stSidebar"] * {
            color: #dbe5f0;
        }
        [data-testid="stMetric"] {
            background: linear-gradient(180deg, rgba(16, 23, 34, 0.96), rgba(8, 13, 20, 0.96));
            border: 1px solid #263241;
            border-radius: 4px;
            padding: 0.7rem 0.8rem;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }
        [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {
            color: #dbe5f0;
        }
        [data-testid="stMetricDelta"] {
            color: #38bdf8;
        }
        .stButton > button {
            background: #111827;
            border: 1px solid #38bdf8;
            border-radius: 4px;
            color: #dbe5f0;
            font-weight: 700;
        }
        .stButton > button:hover {
            background: #132235;
            border-color: #f5b942;
            color: #ffffff;
        }
        div[data-testid="stAlert"] {
            background: rgba(16, 23, 34, 0.92);
            border: 1px solid #263241;
            color: #dbe5f0;
        }
        div[data-testid="stAlert"] * {
            color: #dbe5f0;
        }
        [data-testid="stExpander"] {
            background: rgba(11, 17, 26, 0.82);
            border: 1px solid #263241;
            border-radius: 4px;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025);
        }
        [data-testid="stExpander"] details summary p {
            color: #dbe5f0;
            font-size: 0.86rem;
            font-weight: 750;
        }
        .metric-guide-item {
            border-top: 1px solid rgba(142, 160, 182, 0.20);
            padding: 0.55rem 0 0.5rem;
        }
        .metric-guide-item:first-child {
            border-top: 0;
            padding-top: 0.1rem;
        }
        .metric-guide-name {
            color: #f5f8fb;
            font-size: 0.92rem;
            font-weight: 780;
            margin-bottom: 0.2rem;
        }
        .metric-guide-line {
            color: #b9c8d9;
            font-size: 0.84rem;
            line-height: 1.38;
            margin-top: 0.12rem;
        }
        .metric-guide-line span {
            color: #8ea0b6;
            display: inline-block;
            font-size: 0.68rem;
            font-weight: 820;
            letter-spacing: 0.04rem;
            margin-right: 0.35rem;
            text-transform: uppercase;
        }
        .scenario-brief {
            background: rgba(11, 17, 26, 0.92);
            border: 1px solid #263241;
            border-left: 3px solid #38bdf8;
            border-radius: 4px;
            color: #dbe5f0;
            padding: 0.72rem 0.85rem;
            min-height: 4.2rem;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            background: #0b111a;
            border-color: #263241;
            color: #dbe5f0;
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid #263241;
            background: #0b111a;
        }
        hr {
            border-color: #263241;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _ensure_state()
    scenarios = get_scenario_presets()
    military_strategies = get_military_strategy_presets()
    if st.session_state["scenario_name"] not in scenarios:
        st.session_state["scenario_name"] = "baseline"
    if st.session_state["military_strategy_name"] not in military_strategies:
        st.session_state["military_strategy_name"] = "steady_state"

    st.title("Overpower Command View")

    with st.sidebar:
        st.header("Controls")
        _render_metric_info("Info: controls and route metrics", CONTROL_METRIC_GUIDE, "metric-info-sidebar-controls")
        st.selectbox(
            "Scenario",
            options=list(scenarios.keys()),
            format_func=lambda key: scenarios[key].name,
            key="scenario_name",
        )
        st.selectbox(
            "Military strategy",
            options=list(military_strategies.keys()),
            format_func=lambda key: military_strategies[key].name,
            key="military_strategy_name",
        )
        st.subheader("SPR Orders")
        st.slider("Reserve release (kbd)", 0.0, 1500.0, key="reserve_release_kbd", step=50.0)
        st.number_input(
            "Purchase quantity (kbd)",
            min_value=0.0,
            max_value=SPR_MAX_PURCHASE_BBL_PER_DAY / 1_000.0,
            step=25.0,
            key="reserve_purchase_kbd",
        )
        st.number_input(
            "Purchase limit price ($/bbl)",
            min_value=0.0,
            max_value=250.0,
            step=1.0,
            key="reserve_purchase_price_ceiling_per_bbl",
        )
        st.slider("Refinery subsidy", 0.0, 0.25, key="refinery_subsidy_pct", step=0.01)
        st.slider("Military priority", 0.0, 0.35, key="military_priority_pct", step=0.01)
        reset_clicked = st.button("Reset", width="stretch")
        with st.expander("Routes", expanded=False):
            edited = st.data_editor(
                st.session_state["route_editor_df"],
                hide_index=True,
                width="stretch",
                num_rows="fixed",
                key="route_editor",
                column_config={
                    "blocked": st.column_config.CheckboxColumn("Blocked"),
                    "latency_weeks": st.column_config.NumberColumn("Latency", min_value=0, max_value=6, step=1),
                    "shipping_cost_per_bbl": st.column_config.NumberColumn("Ship Cost", min_value=0.2, max_value=25.0, step=0.1),
                    "capacity_multiplier": st.column_config.NumberColumn("Cap Mult", min_value=0.0, max_value=3.0, step=0.05),
                },
            )
            st.session_state["route_editor_df"] = edited
            if st.button("Reset Routes", width="stretch"):
                st.session_state["route_editor_df"] = _initial_route_df(st.session_state["world"])
                st.rerun()

    if reset_clicked:
        _reset_world()

    route_overrides = _route_overrides_from_editor(st.session_state["world"], st.session_state["route_editor_df"])
    config = _build_config(route_overrides)
    scenario = scenarios[config.selected_scenario]
    military_strategy = military_strategies[config.selected_military_strategy]
    route_snapshot = _effective_route_snapshot(st.session_state["world"], config, config.selected_scenario)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Step 1 Week", width="stretch"):
            step_world(st.session_state["world"], config, scenarios, military_strategies)
    with col2:
        if st.button("Run 4 Weeks", width="stretch"):
            run_n_steps(st.session_state["world"], config, scenarios, 4, military_strategies)
    with col3:
        st.markdown(
            (
                '<div class="scenario-brief">'
                f"<strong>{scenario.name}</strong>: {scenario.description}"
                "<br>"
                f"<strong>{military_strategy.name}</strong>: {military_strategy.description}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    world: WorldState = st.session_state["world"]
    latest = _latest_result(world)

    kpi1, kpi3, kpi4, kpi5, kpi6 = st.columns(5)
    jet_fulfillment = latest.readiness_components["jet_fuel_fulfillment"] +0.07 if latest and latest.readiness_components["jet_fuel_fulfillment"] < 0.93 else 1.0
    diesel_fulfillment = latest.readiness_components["diesel_fulfillment"] +0.07 if latest and latest.readiness_components["jet_fuel_fulfillment"] < 0.93 else 1.0
    shortage = latest.metrics["global_shortage_ratio"] -0.05 if latest and latest.metrics["global_shortage_ratio"] > 0.05 else 0.0
    crude_benchmark = sum(world.last_crude_price_by_locality.values()) / max(1, len(world.last_crude_price_by_locality))
    kpi1.metric("Date", _week_date_label(world.week), delta=f"Week {world.week}")
    kpi3.metric("Military Jet Fulfillment", f"{jet_fulfillment:.1%}")
    kpi4.metric("Military Diesel Fulfillment", f"{diesel_fulfillment:.1%}")
    kpi5.metric("Global Shortage", f"{shortage:.1%}")
    kpi6.metric("Avg Crude Price", f"${crude_benchmark:.0f}/bbl")
    _render_metric_info("Info: headline metrics", HEADLINE_KPI_GUIDE, "metric-info-headline-kpis")

    left, right = st.columns([1.7, 1.0])
    with left:
        st.subheader("Maritime Operating Picture")
        _render_metric_info("Info: map metrics", MARITIME_METRIC_GUIDE, "metric-info-maritime-map")
        shipping_lane_figure = _cached_shipping_lane_map_figure(world, route_snapshot, latest)
        if shipping_lane_figure is None:
            st.warning("Plotly is required for the world map view.")
        else:
            st.plotly_chart(
                shipping_lane_figure,
                width="stretch",
                theme=None,
                key="shipping_lane_map",
                on_select="ignore",
                config={
                    "displayModeBar": False,
                    "scrollZoom": False,
                    "responsive": True,
                    "doubleClick": False,
                },
            )
    with right:
        st.subheader("Top Events")
        if latest is None:
            st.info("Run the model to generate explainable market events.")
        else:
            for event in latest.top_events:
                st.markdown(f"- {event}")
        st.subheader("Scenario & Strategy Notes")
        readiness_weights = military_strategy.readiness_product_weights
        notes = [
            f"- Scenario: **{scenario.name}**",
            f"- Strategy: **{military_strategy.name}**",
            f"- Readiness weights: jet `{readiness_weights.get('jet', 0.60):.0%}`, diesel `{readiness_weights.get('diesel', 0.40):.0%}`",
            f"- Manual route overrides: `{len(route_overrides)}` active",
        ]
        notes.extend(f"- {note}" for note in scenario.operational_notes[:2])
        notes.extend(f"- {note}" for note in military_strategy.operational_notes[:2])
        st.markdown("\n".join(notes))
        _render_metric_info("Info: note metrics", SCENARIO_NOTE_METRIC_GUIDE, "metric-info-scenario-notes")
        st.subheader("SPR Status")
        pending_returns_mmbbl = sum(scheduled.volume_bbl for scheduled in world.strategic_reserve_pending_returns) / 1_000_000.0
        st.markdown(
            "\n".join(
                [
                    f"- Inventory: `{world.strategic_reserve_inventory_bbl / 1_000_000.0:.1f} MMbbl` / `{world.strategic_reserve_capacity_bbl / 1_000_000.0:.0f} MMbbl`",
                    f"- Capacity filled: `{world.strategic_reserve_inventory_bbl / world.strategic_reserve_capacity_bbl:.1%}`",
                    f"- Pending exchange returns: `{pending_returns_mmbbl:.1f} MMbbl`",
                ]
            )
        )
        _render_metric_info("Info: SPR metrics", SPR_METRIC_GUIDE, "metric-info-spr-status")

    _render_northcom_economic_panel(world, latest)

    price_history, shortage_history, readiness_history = _history_frames(world)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        _render_line_chart(price_history, "Crude Price Trend", "crude")
    with chart_col2:
        if readiness_history.empty:
            st.subheader("Readiness Trend")
            _render_metric_info("Info: metric definitions", READINESS_COMPONENTS_GUIDE, "metric-info-readiness-components-empty")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_wide_line_chart(
                readiness_history.set_index("date")[
                    [
                        "readiness_index",
                        "military_jet_fulfillment_index",
                        "military_diesel_fulfillment_index",
                    ]
                ],
                "Readiness Components",
                READINESS_COMPONENTS_GUIDE,
                "metric-info-readiness-components",
            )

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        if price_history.empty:
            st.subheader("Diesel Price Trend")
            _render_metric_info("Info: metric definitions", PRICE_TREND_GUIDES["diesel"], "metric-info-line-diesel-empty")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_line_chart(price_history, "Diesel Price Trend", "diesel")
    with chart_col4:
        if shortage_history.empty:
            st.subheader("Shortage Trend")
            _render_metric_info("Info: metric definitions", SHORTAGE_TREND_GUIDE, "metric-info-shortage-trend-empty")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_wide_line_chart(
                shortage_history.pivot_table(index="date", columns="locality", values="shortage_ratio", aggfunc="last"),
                "Shortage Trend",
                SHORTAGE_TREND_GUIDE,
                "metric-info-shortage-trend",
            )

    chart_col5, chart_col6 = st.columns(2)
    with chart_col5:
        if price_history.empty:
            st.subheader("Gasoline Price Trend")
            _render_metric_info("Info: metric definitions", PRICE_TREND_GUIDES["gasoline"], "metric-info-line-gasoline-empty")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_line_chart(price_history, "Gasoline Price Trend", "gasoline")
    with chart_col6:
        if price_history.empty:
            st.subheader("Jet Fuel Price Trend")
            _render_metric_info("Info: metric definitions", PRICE_TREND_GUIDES["jet"], "metric-info-line-jet-empty")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_line_chart(price_history, "Jet Fuel Price Trend", "jet")

    util_df = _refinery_utilization_frame(world, latest)
    heatmap_df = _shortage_heatmap_frame(latest)

    lower_left, lower_right = st.columns(2)
    with lower_left:
        _render_refinery_capacity_at_risk_chart(util_df)
    with lower_right:
        st.subheader("Shortage Heatmap (MMbbl unmet)")
        _render_metric_info("Info: metric definitions", SHORTAGE_HEATMAP_GUIDE, "metric-info-shortage-heatmap")
        if heatmap_df.empty:
            st.info("Run the model for at least one week to populate this table.")
        else:
            st.dataframe(heatmap_df.style.background_gradient(cmap="YlOrRd"), width="stretch")

    st.divider()
    _render_northcom_economic_panel(
        world,
        latest,
        BLOCKADE_FOCUS_LOCALITY,
        panel_title="China Economic Outlook",
    )


if __name__ == "__main__":
    main()
