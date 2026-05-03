from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from .data import LOCALITY_LABELS, build_world, default_simulation_config, get_scenario_presets
from .sim import (
    DEFAULT_SHIPPING_COST_MULTIPLIER,
    PRODUCTS,
    PolicyControls,
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
SIM_START_DATE = date(2026, 1, 1)
SIM_STEP_DAYS = 7


def _week_date(week: int) -> date:
    return SIM_START_DATE + timedelta(days=week * SIM_STEP_DAYS)


def _week_date_label(week: int) -> str:
    current_date = _week_date(week)
    return f"{current_date:%b} {current_date.day}, {current_date:%Y}"


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


def _render_wide_line_chart(df: pd.DataFrame, title: str) -> None:
    st.subheader(title)
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


def _ensure_state() -> None:
    if "scenario_name" not in st.session_state:
        st.session_state["scenario_name"] = "baseline"
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
    if "world" not in st.session_state:
        st.session_state["world"] = build_world(default_simulation_config(st.session_state["scenario_name"]))
    if "route_editor_df" not in st.session_state:
        st.session_state["route_editor_df"] = _initial_route_df(st.session_state["world"])


def _reset_world() -> None:
    config = default_simulation_config(st.session_state["scenario_name"])
    st.session_state["world"] = build_world(config)
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

    st.title("Overpower Command View")

    with st.sidebar:
        st.header("Controls")
        st.selectbox(
            "Scenario",
            options=list(scenarios.keys()),
            format_func=lambda key: scenarios[key].name,
            key="scenario_name",
        )
        st.slider("Reserve release (kbd)", 0.0, 1500.0, key="reserve_release_kbd", step=50.0)
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
    route_snapshot = _effective_route_snapshot(st.session_state["world"], config, config.selected_scenario)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("Step 1 Week", width="stretch"):
            step_world(st.session_state["world"], config, scenarios)
    with col2:
        if st.button("Run 4 Weeks", width="stretch"):
            run_n_steps(st.session_state["world"], config, scenarios, 4)
    with col3:
        st.markdown(f'<div class="scenario-brief">{scenario.description}</div>', unsafe_allow_html=True)

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

    left, right = st.columns([1.7, 1.0])
    with left:
        st.subheader("Maritime Operating Picture")
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

    price_history, shortage_history, readiness_history = _history_frames(world)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        _render_line_chart(price_history, "Crude Price Trend", "crude")
    with chart_col2:
        if readiness_history.empty:
            st.subheader("Readiness Trend")
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
            )

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        if price_history.empty:
            st.subheader("Diesel Price Trend")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_line_chart(price_history, "Diesel Price Trend", "diesel")
    with chart_col4:
        if shortage_history.empty:
            st.subheader("Shortage Trend")
            st.info("Run the model for at least one week to populate this chart.")
        else:
            _render_wide_line_chart(shortage_history.pivot_table(index="date", columns="locality", values="shortage_ratio", aggfunc="last"), "Shortage Trend")

    util_df = _refinery_utilization_frame(world, latest)
    heatmap_df = _shortage_heatmap_frame(latest)

    lower_left, lower_right = st.columns(2)
    with lower_left:
        _render_refinery_capacity_at_risk_chart(util_df)
    with lower_right:
        st.subheader("Shortage Heatmap (MMbbl unmet)")
        if heatmap_df.empty:
            st.info("Run the model for at least one week to populate this table.")
        else:
            st.dataframe(heatmap_df.style.background_gradient(cmap="YlOrRd"), width="stretch")


if __name__ == "__main__":
    main()
