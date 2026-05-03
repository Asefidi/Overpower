from __future__ import annotations

import pandas as pd
import streamlit as st

from .data import LOCALITY_LABELS, build_world, default_simulation_config, get_scenario_presets
from .sim import PRODUCTS, PolicyControls, SimulationConfig, StepResult, WorldState, run_n_steps, step_world

try:
    import plotly.express as px
except Exception:  # pragma: no cover - optional dependency
    px = None


def _initial_route_df(world: WorldState) -> pd.DataFrame:
    rows = []
    for key, route in world.routes.items():
        if route.origin == route.destination:
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
        }
    for overrides in (scenario.route_overrides, config.route_overrides):
        for key, fields in overrides.items():
            if key not in merged:
                continue
            merged[key].update(fields)
    return merged


def _locality_svg(
    world: WorldState,
    routes: dict[tuple[str, str], dict[str, float | int | bool]],
    result: StepResult | None,
) -> str:
    width = 860
    height = 480
    lines: list[str] = []
    seen_pairs: set[tuple[str, str]] = set()
    for (origin, destination), route in routes.items():
        if origin == destination:
            continue
        pair = tuple(sorted((origin, destination)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        reverse = routes[(destination, origin)]
        blocked = bool(route["blocked"]) or bool(reverse["blocked"])
        x1, y1 = world.localities[origin].position
        x2, y2 = world.localities[destination].position
        stroke = "#d9480f" if blocked else "#0f766e"
        opacity = 0.78 if blocked else 0.18
        capacity = max(float(route["capacity_multiplier"]), float(reverse["capacity_multiplier"]))
        width_px = 3.2 if blocked else 1.0 + capacity * 0.6
        lines.append(
            f'<line x1="{x1 * width:.1f}" y1="{y1 * height:.1f}" x2="{x2 * width:.1f}" y2="{y2 * height:.1f}" stroke="{stroke}" stroke-opacity="{opacity}" stroke-width="{width_px}" />'
        )

    nodes: list[str] = []
    for locality_id, locality in world.localities.items():
        x, y = locality.position
        shortage = result.locality_shortage_ratio.get(locality_id, 0.0) if result else 0.0
        fill = "#ef4444" if shortage > 0.18 else "#f59e0b" if shortage > 0.08 else "#0f766e"
        nodes.append(f'<circle cx="{x * width:.1f}" cy="{y * height:.1f}" r="18" fill="{fill}" fill-opacity="0.95" stroke="#0f172a" stroke-width="2" />')
        nodes.append(
            f'<text x="{x * width:.1f}" y="{y * height + 34:.1f}" text-anchor="middle" font-size="12" font-family="ui-sans-serif, system-ui" fill="#0f172a">{locality.label}</text>'
        )
    return "".join(
        [
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" xmlns="http://www.w3.org/2000/svg">',
            '<rect width="100%" height="100%" rx="24" fill="#f8fafc" />',
            *lines,
            *nodes,
            '</svg>',
        ]
    )


def _history_frames(world: WorldState) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not world.history:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    price_rows = []
    shortage_rows = []
    readiness_rows = []
    for step in world.history:
        for locality_id, crude_price in step.crude_price_by_locality.items():
            price_rows.append(
                {
                    "week": step.week,
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
                    "locality": LOCALITY_LABELS[locality_id],
                    "shortage_ratio": step.locality_shortage_ratio[locality_id],
                }
            )
        readiness_rows.append(
            {
                "week": step.week,
                "readiness_index": step.readiness_index,
                "global_shortage_ratio": step.metrics["global_shortage_ratio"],
                "average_refinery_utilization": step.metrics["average_refinery_utilization"],
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
        rows.append(
            {
                "refinery": refinery.name,
                "locality": LOCALITY_LABELS[refinery.locality],
                "utilization": result.refinery_utilization.get(refinery.id, 0.0),
                "weekly_capacity_mmbbl": refinery.weekly_crude_capacity_bbl / 1_000_000.0,
            }
        )
    return pd.DataFrame(rows).sort_values("utilization", ascending=False)


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


def _winners_losers_frame(world: WorldState, result: StepResult | None) -> pd.DataFrame:
    if result is None:
        return pd.DataFrame()
    baseline_prices = world.history[0].crude_price_by_locality if world.history else world.last_crude_price_by_locality
    rows = []
    for locality_id in world.localities:
        price_delta = result.crude_price_by_locality[locality_id] - baseline_prices[locality_id]
        stress_score = result.locality_shortage_ratio[locality_id] * 100.0 + max(0.0, price_delta) * 0.6 + (world.localities[locality_id].fear_multiplier - 1.0) * 25.0
        rows.append(
            {
                "locality": LOCALITY_LABELS[locality_id],
                "shortage_ratio": result.locality_shortage_ratio[locality_id],
                "crude_price": result.crude_price_by_locality[locality_id],
                "fear_multiplier": world.localities[locality_id].fear_multiplier,
                "stress_score": stress_score,
            }
        )
    return pd.DataFrame(rows).sort_values("stress_score")


def _render_line_chart(df: pd.DataFrame, title: str, y_column: str, color_column: str = "locality") -> None:
    st.subheader(title)
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if px is not None:
        figure = px.line(df, x="week", y=y_column, color=color_column, markers=True)
        figure.update_layout(height=320, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(figure, use_container_width=True)
        return
    chart_df = df.pivot_table(index="week", columns=color_column, values=y_column, aggfunc="last")
    st.line_chart(chart_df)


def _render_bar_chart(df: pd.DataFrame, title: str, x_column: str, y_column: str) -> None:
    st.subheader(title)
    if df.empty:
        st.info("Run the model for at least one week to populate this chart.")
        return
    if px is not None:
        figure = px.bar(df, x=x_column, y=y_column, color=y_column, color_continuous_scale="Tealgrn")
        figure.update_layout(height=340, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(figure, use_container_width=True)
        return
    st.bar_chart(df.set_index(x_column)[y_column])


def _ensure_state() -> None:
    if "scenario_name" not in st.session_state:
        st.session_state["scenario_name"] = "baseline"
    if "reserve_release_kbd" not in st.session_state:
        st.session_state["reserve_release_kbd"] = 0.0
    if "refinery_subsidy_pct" not in st.session_state:
        st.session_state["refinery_subsidy_pct"] = 0.0
    if "military_priority_pct" not in st.session_state:
        st.session_state["military_priority_pct"] = 0.0
    if "shipping_cost_multiplier" not in st.session_state:
        st.session_state["shipping_cost_multiplier"] = 1.0
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
    _ensure_state()
    scenarios = get_scenario_presets()

    st.title("Overpower")
    st.caption("Agent-based fossil fuel supply chain MVP for weekly disruption wargaming.")

    with st.sidebar:
        st.header("Scenario Controls")
        st.caption("Scenario and policy edits affect the next simulation step. Use Reset World for a clean A/B comparison.")
        st.selectbox(
            "Scenario",
            options=list(scenarios.keys()),
            format_func=lambda key: scenarios[key].name,
            key="scenario_name",
        )
        st.slider("Reserve release (kbd)", 0.0, 1500.0, key="reserve_release_kbd", step=50.0)
        st.slider("Refinery subsidy boost", 0.0, 0.25, key="refinery_subsidy_pct", step=0.01)
        st.slider("Military priority boost", 0.0, 0.35, key="military_priority_pct", step=0.01)
        st.slider("Global shipping cost multiplier", 0.75, 2.0, key="shipping_cost_multiplier", step=0.05)
        reset_clicked = st.button("Reset World", use_container_width=True)
        with st.expander("Route Overrides", expanded=False):
            st.caption("Every directed route can be blocked or repriced here. These overrides stack on top of the selected scenario.")
            edited = st.data_editor(
                st.session_state["route_editor_df"],
                hide_index=True,
                use_container_width=True,
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
            if st.button("Reset Route Table", use_container_width=True):
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
        if st.button("Step 1 Week", use_container_width=True):
            step_world(st.session_state["world"], config, scenarios)
    with col2:
        if st.button("Run 4 Weeks", use_container_width=True):
            run_n_steps(st.session_state["world"], config, scenarios, 4)
    with col3:
        st.info(scenario.description)

    world: WorldState = st.session_state["world"]
    latest = _latest_result(world)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    readiness = latest.readiness_index if latest else 100.0
    shortage = latest.metrics["global_shortage_ratio"] if latest else 0.0
    crude_benchmark = sum(world.last_crude_price_by_locality.values()) / max(1, len(world.last_crude_price_by_locality))
    kpi1.metric("Week", world.week)
    kpi2.metric("Strategic Readiness", f"{readiness:.1f}")
    kpi3.metric("Global Shortage", f"{shortage:.1%}")
    kpi4.metric("Avg Crude Price", f"${crude_benchmark:.0f}/bbl")

    left, right = st.columns([1.1, 1.3])
    with left:
        st.subheader("Locality Route Graph")
        st.caption("Green nodes are stable, amber nodes are strained, and red nodes are experiencing visible shortages.")
        st.components.v1.html(_locality_svg(world, route_snapshot, latest), height=500)
    with right:
        st.subheader("Top Events")
        if latest is None:
            st.info("Run the model to generate explainable market events.")
        else:
            for event in latest.top_events:
                st.markdown(f"- {event}")
        st.subheader("Scenario Notes")
        st.markdown(
            "\n".join(
                [
                    f"- Scenario: **{scenario.name}**",
                    f"- Policy overlays: reserve release `{config.policy_controls.reserve_release_kbd:.0f} kbd`, subsidy `{config.policy_controls.refinery_subsidy_pct:.0%}`, military priority `{config.policy_controls.military_priority_pct:.0%}`",
                    f"- Manual route overrides: `{len(route_overrides)}` active",
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
            st.subheader("Readiness Trend")
            st.line_chart(readiness_history.set_index("week")[["readiness_index", "average_refinery_utilization"]])

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
            st.subheader("Shortage Trend")
            st.line_chart(shortage_history.pivot_table(index="week", columns="locality", values="shortage_ratio", aggfunc="last"))

    util_df = _refinery_utilization_frame(world, latest).head(12)
    heatmap_df = _shortage_heatmap_frame(latest)
    winners_df = _winners_losers_frame(world, latest)

    lower_left, lower_right = st.columns(2)
    with lower_left:
        _render_bar_chart(util_df, "Refinery Utilization Ranking", "refinery", "utilization")
    with lower_right:
        st.subheader("Shortage Heatmap (MMbbl unmet)")
        if heatmap_df.empty:
            st.info("Run the model for at least one week to populate this table.")
        else:
            st.dataframe(heatmap_df.style.background_gradient(cmap="YlOrRd"), use_container_width=True)

    st.subheader("Winners / Losers")
    if winners_df.empty:
        st.info("Run the model for at least one week to populate this table.")
    else:
        winners = winners_df.head(3).assign(status="Most Resilient")
        losers = winners_df.tail(3).sort_values("stress_score", ascending=False).assign(status="Most Stressed")
        summary = pd.concat([winners, losers], ignore_index=True)
        st.dataframe(summary, use_container_width=True, hide_index=True)

    st.subheader("Market Snapshot")
    snapshot_rows = []
    for locality_id, locality in world.localities.items():
        snapshot_rows.append(
            {
                "locality": locality.label,
                "fear_multiplier": locality.fear_multiplier,
                "crude_inventory_mmbbl": world.crude_inventory[locality_id] / 1_000_000.0,
                "gasoline_inventory_mmbbl": world.product_inventory[locality_id]["gasoline"] / 1_000_000.0,
                "diesel_inventory_mmbbl": world.product_inventory[locality_id]["diesel"] / 1_000_000.0,
                "jet_inventory_mmbbl": world.product_inventory[locality_id]["jet"] / 1_000_000.0,
            }
        )
    st.dataframe(pd.DataFrame(snapshot_rows), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
