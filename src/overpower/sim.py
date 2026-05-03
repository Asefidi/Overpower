from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from math import cos, exp, pi, sin
from typing import Any

PRODUCTS = ("gasoline", "diesel", "jet")
SECTORS = ("heavy_logistics", "aviation", "agriculture", "light_logistics", "other")
HOUSEHOLD_QUARTILES = ("q1", "q2", "q3", "q4")
STRATEGIC_PRODUCTS = {("heavy_logistics", "diesel"), ("aviation", "jet"), ("military", "diesel"), ("military", "jet")}
BASE_PRODUCT_PRICES = {"gasoline": 112.0, "diesel": 126.0, "jet": 138.0}
DEFAULT_SHIPPING_COST_MULTIPLIER = 1.0
SCENARIO_NEUTRAL_SHIPPING_COST_MULTIPLIER = 1.2
DEFAULT_BASELINE_WARM_START_WEEKS = 16
FEAR_MIN = 0.85
FEAR_MAX = 3.0
BASELINE_FEAR_MAX = 1.08
CRUDE_SUPPLY_TRANCHES = ((0.50, 0.0), (0.30, 5.0), (0.20, 13.0))
CRUDE_DEMAND_TRANCHES = ((0.56, 1.00), (0.30, 0.92), (0.14, 0.82))
PRODUCT_SUPPLY_TRANCHES = ((0.58, 1.00), (0.28, 1.05), (0.14, 1.14))
PRODUCT_DEMAND_TRANCHES = ((0.55, 1.00), (0.30, 0.90), (0.15, 0.76))
PRODUCT_ROUTE_CAPACITY_SHARE = 0.68
PRODUCT_ORDER_BID_FLOOR_MULTIPLIER = 1.00
BASELINE_LOCAL_PRODUCT_RESERVE_SHARE = 0.68
STRESSED_LOCAL_PRODUCT_RESERVE_SHARE = 0.90
MILITARY_LOCAL_PRODUCT_RESERVE_SHARE = 0.82
BASELINE_COMMERCIAL_MAX_SHORTAGE = {"gasoline": 0.10, "diesel": 0.07, "jet": 0.07}
PRODUCT_CRUDE_PASS_THROUGH = {"gasoline": 0.96, "diesel": 1.03, "jet": 1.06}
PRODUCT_CONVERSION_PREMIUM = {"gasoline": 12.0, "diesel": 15.0, "jet": 17.0}
PRODUCT_TARGET_MARGIN = {"gasoline": 8.0, "diesel": 10.0, "jet": 11.0}
PRODUCT_ELASTICITY = {"gasoline": -0.18, "diesel": -0.10, "jet": -0.12}
MILITARY_MIN_BID_MULTIPLIER = {"gasoline": 0.0, "diesel": 4.35, "jet": 4.75}
MILITARY_CONFLICT_DEMAND_RESPONSE = {"gasoline": 0.0, "diesel": 0.18, "jet": 0.28}
MILITARY_CONFLICT_BID_RESPONSE = {"gasoline": 0.0, "diesel": 0.40, "jet": 0.48}
SPR_STORAGE_CAPACITY_BBL = 714_000_000.0
DEFAULT_SPR_INVENTORY_BBL = 397_900_000.0
SPR_BOOK_COST_PER_BBL = 29.70
SPR_MAX_DRAWDOWN_BBL_PER_DAY = 4_400_000.0
SPR_MAX_PURCHASE_BBL_PER_DAY = 1_000_000.0
SPR_MARKET_NODE = "NORTHCOM"
COUNTRY_LOCALITY_CRUDE_EMBARGOES = {
    ("Venezuela", "EUCOM"),
    ("EUCOM", "Venezuela"),
    ("Venezuela", "NORTHCOM"),
    ("NORTHCOM", "Venezuela"),
}
RESERVE_RELEASE_WEIGHTS = {
    "NORTHCOM": 0.40,
    "EUCOM": 0.20,
    "INDOPACOM": 0.18,
    "AFRICOM": 0.08,
    "SOUTHCOM": 0.07,
    "CENTCOM": 0.04,
    "RUSSIA": 0.02,
    "CHINA": 0.01,
}
STRATEGIC_LOCALITY_WEIGHTS = {
    "NORTHCOM": 0.20,
    "EUCOM": 0.22,
    "RUSSIA": 0.04,
    "CENTCOM": 0.12,
    "IRAN": 0.04,
    "INDOPACOM": 0.20,
    "CHINA": 0.10,
    "AFRICOM": 0.05,
    "SOUTHCOM": 0.03,
}
DEFAULT_READINESS_PRODUCT_WEIGHTS = {"jet": 0.60, "diesel": 0.40}
HOUSEHOLD_AFFORDABILITY_SEGMENT_WEIGHTS = {"q1": 1.55, "q2": 1.22, "q3": 1.00, "q4": 0.78}
INDUSTRIAL_SEGMENT_OUTPUT_WEIGHTS = {
    "heavy_logistics": 1.18,
    "aviation": 1.12,
    "agriculture": 1.08,
    "light_logistics": 0.94,
    "other": 0.68,
}
INDUSTRIAL_PRODUCT_CRITICALITY = {
    "heavy_logistics": {"gasoline": 0.36, "diesel": 1.00, "jet": 0.18},
    "aviation": {"gasoline": 0.12, "diesel": 0.20, "jet": 1.00},
    "agriculture": {"gasoline": 0.42, "diesel": 1.00, "jet": 0.08},
    "light_logistics": {"gasoline": 0.78, "diesel": 0.88, "jet": 0.12},
    "other": {"gasoline": 0.42, "diesel": 0.54, "jet": 0.36},
}
INDUSTRIAL_PRICE_DRAG_FACTOR = 0.32
# Calibrated as an official-data proxy: EIA MECS 2022 Table 6.1 reports fuel
# consumption per dollar of shipments/value added, MECS fuel-switching tables
# bound short-run flexibility, and BEA Gross Output frames output as industry
# sales/receipts. Source pages:
# https://www.eia.gov/consumption/manufacturing/data/2022/
# https://www.eia.gov/totalenergy/data/monthly/
# https://www.bea.gov/data/industries/gross-output-by-industry
INDUSTRIAL_OUTPUT_SIGMOID_STEEPNESS = 8.0
INDUSTRIAL_OUTPUT_SIGMOID_MIDPOINT = 0.55


@dataclass(slots=True)
class PolicyControls:
    reserve_release_kbd: float = 0.0
    reserve_release_mode: str = "exchange"
    reserve_purchase_kbd: float = 0.0
    reserve_purchase_price_ceiling_per_bbl: float = 79.0
    reserve_exchange_return_weeks: int = 52
    reserve_exchange_premium_pct: float = 0.03
    refinery_subsidy_pct: float = 0.0
    military_priority_pct: float = 0.0
    shipping_cost_multiplier: float = DEFAULT_SHIPPING_COST_MULTIPLIER


def neutral_policy_controls() -> PolicyControls:
    return PolicyControls(shipping_cost_multiplier=SCENARIO_NEUTRAL_SHIPPING_COST_MULTIPLIER)


@dataclass(slots=True)
class SimulationConfig:
    seed: int = 0
    start_week: int = 0
    selected_scenario: str = "baseline"
    selected_military_strategy: str = "steady_state"
    route_overrides: dict[tuple[str, str], dict[str, float | int | bool]] = field(default_factory=dict)
    policy_controls: PolicyControls = field(default_factory=PolicyControls)
    demand_sensitivity: float = 0.20
    inventory_cover_weeks: float = 1.35
    warm_start_weeks: int = DEFAULT_BASELINE_WARM_START_WEEKS


@dataclass(slots=True)
class LocalityState:
    id: str
    label: str
    gdp_per_capita: float
    gini: float
    baseline_crude_production_bbl_week: float
    baseline_refinery_capacity_bbl_week: float
    baseline_refinery_throughput_bbl_week: float
    base_product_demand_bbl_week: dict[str, float]
    fear_multiplier: float = 1.0
    position: tuple[float, float] = (0.5, 0.5)


@dataclass(slots=True)
class CrudeProducerAgent:
    id: str
    name: str
    country: str
    locality: str
    baseline_supply_bbl_week: float
    cost_floor_per_bbl: float
    risk_weight: float


@dataclass(slots=True)
class RefineryAgent:
    id: str
    name: str
    country: str
    locality: str
    weekly_crude_capacity_bbl: float
    baseline_utilization: float
    complexity_score: float
    processing_cost_per_bbl: float
    yield_shares: dict[str, float]


@dataclass(slots=True)
class DemandAgent:
    id: str
    name: str
    locality: str
    agent_kind: str
    segment: str
    base_demand_bbl_week: dict[str, float]
    price_priority: dict[str, float]
    income_multiplier: float
    backlog_bbl: dict[str, float] = field(default_factory=lambda: {product: 0.0 for product in PRODUCTS})


@dataclass(slots=True)
class RouteState:
    origin: str
    destination: str
    latency_weeks: int
    shipping_cost_per_bbl: float
    capacity_multiplier: float = 1.0
    blocked: bool = False
    base_capacity_bbl: float = 0.0


@dataclass(slots=True)
class Shipment:
    origin: str
    destination: str
    volume_bbl: float
    arrival_week: int
    unit_cost_per_bbl: float
    supplier_id: str
    buyer_id: str
    commodity: str = "crude"


@dataclass(slots=True)
class ReserveReturn:
    arrival_week: int
    volume_bbl: float
    premium_bbl: float
    source: str = "exchange"


@dataclass(slots=True)
class ReserveOperationResult:
    distribution: dict[str, float] = field(default_factory=dict)
    released_bbl: float = 0.0
    release_mode: str = ""
    purchased_bbl: float = 0.0
    returned_bbl: float = 0.0
    sale_revenue_usd: float = 0.0
    purchase_cost_usd: float = 0.0


@dataclass(slots=True)
class ProductAuctionResult:
    trades: dict[tuple[str, str], list[tuple[float, float]]]
    military_demand_by_product: dict[str, float]
    military_fulfilled_by_product: dict[str, float]
    agent_product_outcomes: dict[tuple[str, str], dict[str, Any]]


@dataclass(slots=True)
class ScenarioPreset:
    name: str
    description: str
    operational_notes: tuple[str, ...] = ()
    route_overrides: dict[tuple[str, str], dict[str, float | int | bool]] = field(default_factory=dict)
    locality_fear_shocks: dict[str, float] = field(default_factory=dict)
    producer_supply_shocks: dict[str, float] = field(default_factory=dict)
    producer_country_shocks: dict[str, float] = field(default_factory=dict)
    refinery_capacity_shocks: dict[str, float] = field(default_factory=dict)
    refinery_country_shocks: dict[str, float] = field(default_factory=dict)
    military_demand_shocks: dict[str, float] = field(default_factory=dict)
    policy_defaults: PolicyControls = field(default_factory=neutral_policy_controls)


@dataclass(slots=True)
class MilitaryStrategyPreset:
    name: str
    description: str
    operational_notes: tuple[str, ...] = ()
    product_demand_multipliers: dict[str, float] = field(default_factory=dict)
    locality_demand_shocks: dict[str, float] = field(default_factory=dict)
    product_bid_multipliers: dict[str, float] = field(default_factory=dict)
    readiness_product_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_READINESS_PRODUCT_WEIGHTS))


@dataclass(slots=True)
class StepResult:
    week: int
    crude_price_by_locality: dict[str, float]
    product_prices: dict[str, dict[str, float]]
    unmet_demand_by_locality_product: dict[str, dict[str, float]]
    refinery_utilization: dict[str, float]
    readiness_index: float
    readiness_components: dict[str, float]
    top_events: list[str]
    locality_shortage_ratio: dict[str, float]
    product_fulfillment_ratio: dict[str, dict[str, float]]
    locality_crude_inventory_bbl: dict[str, float]
    locality_product_inventory_bbl: dict[str, dict[str, float]]
    strategic_reserve_inventory_bbl: float
    strategic_reserve_market_value_usd: float
    strategic_reserve_capacity_ratio: float
    strategic_reserve_released_bbl: float
    strategic_reserve_purchased_bbl: float
    strategic_reserve_returned_bbl: float
    household_fuel_affordability: dict[str, dict[str, float]]
    industrial_output_at_risk: dict[str, dict[str, float]]
    industrial_output: dict[str, dict[str, float]]
    metrics: dict[str, float]


@dataclass(slots=True)
class WorldState:
    week: int
    localities: dict[str, LocalityState]
    producers: list[CrudeProducerAgent]
    refiners: list[RefineryAgent]
    demand_agents: list[DemandAgent]
    routes: dict[tuple[str, str], RouteState]
    shipments_in_transit: list[Shipment]
    crude_inventory: dict[str, float]
    product_inventory: dict[str, dict[str, float]]
    product_cost_basis: dict[str, dict[str, float]]
    strategic_reserve_inventory_bbl: float
    strategic_reserve_capacity_bbl: float
    strategic_reserve_cash_usd: float
    strategic_reserve_pending_returns: list[ReserveReturn]
    last_crude_price_by_locality: dict[str, float]
    last_product_prices: dict[str, dict[str, float]]
    metrics: dict[str, float] = field(default_factory=dict)
    history: list[StepResult] = field(default_factory=list)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _industrial_oil_sigmoid(oil_input_ratio: float) -> float:
    exponent = -INDUSTRIAL_OUTPUT_SIGMOID_STEEPNESS * (
        oil_input_ratio - INDUSTRIAL_OUTPUT_SIGMOID_MIDPOINT
    )
    return 1.0 / (1.0 + exp(exponent))


def _industrial_output_index(oil_input_ratio: float) -> float:
    ratio = _clamp(oil_input_ratio, 0.0, 1.0)
    low = _industrial_oil_sigmoid(0.0)
    high = _industrial_oil_sigmoid(1.0)
    current = _industrial_oil_sigmoid(ratio)
    return _clamp(100.0 * _safe_div(current - low, high - low), 0.0, 100.0)


def _industrial_economic_output_index(oil_input_ratio: float, output_at_risk: float) -> float:
    physical_index = _industrial_output_index(oil_input_ratio)
    risk_adjusted_index = 100.0 * (1.0 - _clamp(output_at_risk, 0.0, 1.0))
    return _clamp(min(physical_index, risk_adjusted_index), 0.0, 100.0)


def _weighted_average(trades: list[tuple[float, float]], fallback: float) -> float:
    volume = sum(volume for volume, _ in trades)
    if volume <= 0:
        return fallback
    return sum(volume * price for volume, price in trades) / volume


def _stable_noise(seed: int, week: int, key: str) -> float:
    value = (seed + 31) * 1_000_003 + (week + 17) * 97_409
    for char in key:
        value = (value * 16_777_619) ^ ord(char)
        value &= 0xFFFFFFFF
    return (value / 0xFFFFFFFF) * 2.0 - 1.0


def _is_baseline_scenario(scenario: ScenarioPreset) -> bool:
    return scenario.name == "Baseline"


def default_military_strategy() -> MilitaryStrategyPreset:
    return MilitaryStrategyPreset(
        name="Steady State",
        description="Baseline operational posture with steady military fuel purchases and the default jet/diesel readiness balance.",
        operational_notes=(
            "Posture: no additional operational surge beyond public DoD operational-energy demand.",
            "Demand effect: military fuel buyers retain their baseline jet and diesel purchase profile.",
            "Readiness effect: readiness weights remain 60% jet fuel fulfillment and 40% diesel fulfillment.",
        ),
        product_demand_multipliers={"gasoline": 1.0, "diesel": 1.0, "jet": 1.0},
        product_bid_multipliers={"gasoline": 1.0, "diesel": 1.0, "jet": 1.0},
        readiness_product_weights=dict(DEFAULT_READINESS_PRODUCT_WEIGHTS),
    )


def _select_military_strategy(
    config: SimulationConfig,
    military_strategies: dict[str, MilitaryStrategyPreset] | None,
) -> MilitaryStrategyPreset:
    if not military_strategies:
        return default_military_strategy()
    return military_strategies.get(config.selected_military_strategy, military_strategies.get("steady_state", default_military_strategy()))


def _readiness_product_weights(strategy: MilitaryStrategyPreset) -> dict[str, float]:
    jet = max(0.0, strategy.readiness_product_weights.get("jet", DEFAULT_READINESS_PRODUCT_WEIGHTS["jet"]))
    diesel = max(0.0, strategy.readiness_product_weights.get("diesel", DEFAULT_READINESS_PRODUCT_WEIGHTS["diesel"]))
    total = jet + diesel
    if total <= 0.0:
        return dict(DEFAULT_READINESS_PRODUCT_WEIGHTS)
    return {"jet": jet / total, "diesel": diesel / total}


def _seasonal_multiplier(week: int, product: str, segment: str) -> float:
    week_in_year = (week - 1) % 52
    if product == "gasoline":
        multiplier = 1.0 + 0.070 * sin(2.0 * pi * (week_in_year - 17) / 52.0)
        if segment.startswith("q") or segment == "light_logistics":
            multiplier += 0.025 * sin(2.0 * pi * (week_in_year - 21) / 52.0)
        return _clamp(multiplier, 0.88, 1.14)
    if product == "diesel":
        winter = 0.035 * cos(2.0 * pi * (week_in_year - 1) / 52.0)
        harvest = 0.035 * sin(2.0 * pi * (week_in_year - 33) / 52.0)
        segment_boost = 0.018 if segment in {"agriculture", "heavy_logistics"} else 0.0
        return _clamp(1.0 + winter + harvest + segment_boost, 0.90, 1.13)
    summer_travel = 0.060 * sin(2.0 * pi * (week_in_year - 20) / 52.0)
    holiday_travel = 0.025 * cos(2.0 * pi * (week_in_year - 50) / 52.0)
    segment_boost = 0.022 if segment == "aviation" else 0.0
    return _clamp(1.0 + summer_travel + holiday_travel + segment_boost, 0.90, 1.13)


def _segment_elasticity(agent: DemandAgent, product: str) -> float:
    elasticity = PRODUCT_ELASTICITY[product]
    if agent.agent_kind == "military":
        return elasticity * 0.08
    if agent.agent_kind == "household":
        elasticity *= 1.25
        if agent.segment == "q1":
            elasticity *= 1.15
        elif agent.segment == "q4":
            elasticity *= 0.82
    if (agent.segment, product) in STRATEGIC_PRODUCTS:
        elasticity *= 0.45
    elif agent.segment in {"aviation", "heavy_logistics", "agriculture"}:
        elasticity *= 0.72
    return elasticity


def _add_product_inventory(
    world: WorldState,
    locality_id: str,
    product: str,
    volume_bbl: float,
    unit_cost_per_bbl: float,
) -> None:
    if volume_bbl <= 0.0:
        return
    current_volume = world.product_inventory[locality_id][product]
    current_cost = world.product_cost_basis[locality_id][product]
    total_volume = current_volume + volume_bbl
    blended_cost = (current_volume * current_cost + volume_bbl * unit_cost_per_bbl) / max(total_volume, 1.0)
    world.product_inventory[locality_id][product] = total_volume
    world.product_cost_basis[locality_id][product] = _clamp(
        blended_cost,
        BASE_PRODUCT_PRICES[product] * 0.45,
        BASE_PRODUCT_PRICES[product] * 4.0,
    )


def _draw_product_inventory(world: WorldState, locality_id: str, product: str, volume_bbl: float) -> float:
    available = world.product_inventory[locality_id][product]
    drawn = min(max(0.0, volume_bbl), available)
    world.product_inventory[locality_id][product] = available - drawn
    return drawn


def _in_transit_service_credit(latency_weeks: int) -> float:
    if latency_weeks <= 0:
        return 1.0
    return _clamp(1.0 - latency_weeks * 0.03, 0.90, 0.97)


def _copy_routes(routes: dict[tuple[str, str], RouteState]) -> dict[tuple[str, str], RouteState]:
    return {key: replace(route) for key, route in routes.items()}


def _effective_policy(config: SimulationConfig, scenario: ScenarioPreset) -> PolicyControls:
    return PolicyControls(
        reserve_release_kbd=scenario.policy_defaults.reserve_release_kbd + config.policy_controls.reserve_release_kbd,
        reserve_release_mode=config.policy_controls.reserve_release_mode,
        reserve_purchase_kbd=scenario.policy_defaults.reserve_purchase_kbd + config.policy_controls.reserve_purchase_kbd,
        reserve_purchase_price_ceiling_per_bbl=config.policy_controls.reserve_purchase_price_ceiling_per_bbl,
        reserve_exchange_return_weeks=config.policy_controls.reserve_exchange_return_weeks,
        reserve_exchange_premium_pct=config.policy_controls.reserve_exchange_premium_pct,
        refinery_subsidy_pct=scenario.policy_defaults.refinery_subsidy_pct + config.policy_controls.refinery_subsidy_pct,
        military_priority_pct=scenario.policy_defaults.military_priority_pct + config.policy_controls.military_priority_pct,
        shipping_cost_multiplier=scenario.policy_defaults.shipping_cost_multiplier * config.policy_controls.shipping_cost_multiplier,
    )


def _effective_routes(
    world: WorldState,
    config: SimulationConfig,
    scenario: ScenarioPreset,
    policy: PolicyControls,
) -> dict[tuple[str, str], RouteState]:
    routes = _copy_routes(world.routes)
    for override_source in (scenario.route_overrides, config.route_overrides):
        for key, fields in override_source.items():
            if key not in routes:
                continue
            route = routes[key]
            if "latency_weeks" in fields:
                route.latency_weeks = int(fields["latency_weeks"])
            if "shipping_cost_per_bbl" in fields:
                route.shipping_cost_per_bbl = float(fields["shipping_cost_per_bbl"])
            if "capacity_multiplier" in fields:
                route.capacity_multiplier = float(fields["capacity_multiplier"])
            if "blocked" in fields:
                route.blocked = bool(fields["blocked"])
    for route in routes.values():
        route.capacity_multiplier = _clamp(route.capacity_multiplier, 0.0, 3.0)
        route.shipping_cost_per_bbl *= max(0.2, policy.shipping_cost_multiplier)
        if route.origin != route.destination and not route.blocked:
            route.shipping_cost_per_bbl *= 1.0 + _stable_noise(
                config.seed,
                world.week,
                f"route:{route.origin}:{route.destination}",
            ) * 0.035
    return routes


def _crude_benchmark(prices: dict[str, float]) -> float:
    if not prices:
        return 70.0
    return sum(prices.values()) / len(prices)


def _reserve_release_mode(policy: PolicyControls) -> str:
    mode = policy.reserve_release_mode.lower().strip()
    if mode not in {"exchange", "sale"}:
        return "exchange"
    return mode


def _reserve_distribution_shares(world: WorldState) -> dict[str, float]:
    available_weights = {
        locality: weight
        for locality, weight in RESERVE_RELEASE_WEIGHTS.items()
        if locality in world.crude_inventory
    }
    total_weight = sum(available_weights.values())
    if total_weight <= 0:
        return {}
    return {
        locality: weight / total_weight
        for locality, weight in available_weights.items()
    }


def _resolve_reserve_returns(world: WorldState) -> float:
    returned_bbl = 0.0
    remaining_returns: list[ReserveReturn] = []
    for scheduled_return in world.strategic_reserve_pending_returns:
        if scheduled_return.arrival_week > world.week:
            remaining_returns.append(scheduled_return)
            continue
        capacity_room = max(0.0, world.strategic_reserve_capacity_bbl - world.strategic_reserve_inventory_bbl)
        accepted_bbl = min(scheduled_return.volume_bbl, capacity_room)
        if accepted_bbl > 0.0:
            world.strategic_reserve_inventory_bbl += accepted_bbl
            returned_bbl += accepted_bbl
        overflow_bbl = scheduled_return.volume_bbl - accepted_bbl
        if overflow_bbl > 1.0:
            remaining_returns.append(
                replace(
                    scheduled_return,
                    arrival_week=world.week + 1,
                    volume_bbl=overflow_bbl,
                    premium_bbl=max(0.0, scheduled_return.premium_bbl - accepted_bbl),
                )
            )
    world.strategic_reserve_pending_returns = remaining_returns
    return returned_bbl


def _apply_reserve_policy(world: WorldState, policy: PolicyControls) -> ReserveOperationResult:
    operation = ReserveOperationResult(returned_bbl=_resolve_reserve_returns(world))
    benchmark_price = _crude_benchmark(world.last_crude_price_by_locality)

    if policy.reserve_release_kbd > 0:
        requested_release_bbl = policy.reserve_release_kbd * 1_000.0 * 7.0
        weekly_drawdown_cap_bbl = SPR_MAX_DRAWDOWN_BBL_PER_DAY * 7.0
        released_bbl = min(
            requested_release_bbl,
            weekly_drawdown_cap_bbl,
            world.strategic_reserve_inventory_bbl,
        )
        distribution_shares = _reserve_distribution_shares(world)
        if released_bbl > 0.0 and distribution_shares:
            world.strategic_reserve_inventory_bbl -= released_bbl
            operation.released_bbl = released_bbl
            operation.release_mode = _reserve_release_mode(policy)
            for locality, share in distribution_shares.items():
                addition = released_bbl * share
                world.crude_inventory[locality] += addition
                operation.distribution[locality] = addition
            if operation.release_mode == "sale":
                operation.sale_revenue_usd = released_bbl * benchmark_price
                world.strategic_reserve_cash_usd += operation.sale_revenue_usd
            else:
                premium_bbl = released_bbl * max(0.0, policy.reserve_exchange_premium_pct)
                world.strategic_reserve_pending_returns.append(
                    ReserveReturn(
                        arrival_week=world.week + max(1, int(policy.reserve_exchange_return_weeks)),
                        volume_bbl=released_bbl + premium_bbl,
                        premium_bbl=premium_bbl,
                    )
                )

    if policy.reserve_purchase_kbd > 0 and benchmark_price <= policy.reserve_purchase_price_ceiling_per_bbl:
        market_node = SPR_MARKET_NODE if SPR_MARKET_NODE in world.crude_inventory else next(iter(world.crude_inventory))
        locality = world.localities[market_node]
        requested_purchase_bbl = policy.reserve_purchase_kbd * 1_000.0 * 7.0
        weekly_purchase_cap_bbl = SPR_MAX_PURCHASE_BBL_PER_DAY * 7.0
        capacity_room_bbl = max(0.0, world.strategic_reserve_capacity_bbl - world.strategic_reserve_inventory_bbl)
        local_operating_floor_bbl = locality.baseline_refinery_throughput_bbl_week * 0.70
        available_market_slack_bbl = max(0.0, world.crude_inventory[market_node] - local_operating_floor_bbl)
        purchased_bbl = min(
            requested_purchase_bbl,
            weekly_purchase_cap_bbl,
            capacity_room_bbl,
            available_market_slack_bbl,
        )
        if purchased_bbl > 0.0:
            world.crude_inventory[market_node] -= purchased_bbl
            world.strategic_reserve_inventory_bbl += purchased_bbl
            operation.purchased_bbl = purchased_bbl
            operation.purchase_cost_usd = purchased_bbl * benchmark_price
            world.strategic_reserve_cash_usd -= operation.purchase_cost_usd

    return operation


def _resolve_arrivals(world: WorldState) -> None:
    remaining: list[Shipment] = []
    for shipment in world.shipments_in_transit:
        if shipment.arrival_week <= world.week:
            if shipment.commodity == "crude":
                world.crude_inventory[shipment.destination] += shipment.volume_bbl
            elif shipment.commodity in PRODUCTS:
                _add_product_inventory(
                    world,
                    shipment.destination,
                    shipment.commodity,
                    shipment.volume_bbl,
                    shipment.unit_cost_per_bbl,
                )
        else:
            remaining.append(shipment)
    world.shipments_in_transit = remaining


def _pre_clear_locality_fear(world: WorldState, scenario: ScenarioPreset) -> None:
    for locality_id, locality in world.localities.items():
        scenario_fear = scenario.locality_fear_shocks.get(locality_id, 0.0)
        target_fear = 1.0 + scenario_fear
        locality.fear_multiplier = _clamp(locality.fear_multiplier * 0.38 + target_fear * 0.62, FEAR_MIN, FEAR_MAX)


def _post_clear_locality_fear(
    world: WorldState,
    scenario: ScenarioPreset,
    locality_shortage_ratio: dict[str, float],
) -> None:
    for locality_id, locality in world.localities.items():
        scenario_fear = scenario.locality_fear_shocks.get(locality_id, 0.0)
        if _is_baseline_scenario(scenario):
            shortage_fear = max(0.0, locality_shortage_ratio[locality_id] - 0.08) * 0.20
        else:
            shortage_fear = locality_shortage_ratio[locality_id] * 1.05
        target_fear = 1.0 + scenario_fear + shortage_fear
        high = BASELINE_FEAR_MAX if _is_baseline_scenario(scenario) else FEAR_MAX
        locality.fear_multiplier = _clamp(locality.fear_multiplier * 0.45 + target_fear * 0.55, FEAR_MIN, high)


def _is_country_locality_crude_embargoed(producer: CrudeProducerAgent, refinery: RefineryAgent) -> bool:
    return (
        (producer.country, refinery.locality) in COUNTRY_LOCALITY_CRUDE_EMBARGOES
        or (producer.locality, refinery.country) in COUNTRY_LOCALITY_CRUDE_EMBARGOES
    )


def _producer_supply_offer(
    producer: CrudeProducerAgent,
    world: WorldState,
    config: SimulationConfig,
    scenario: ScenarioPreset,
) -> tuple[float, float]:
    locality = world.localities[producer.locality]
    supply_shock = scenario.producer_supply_shocks.get(producer.locality, 1.0)
    supply_shock *= scenario.producer_country_shocks.get(producer.country, 1.0)
    operating_factor = 1.0 + _stable_noise(config.seed, world.week, f"supply:{producer.id}") * 0.045
    effective_supply = max(0.04, supply_shock * operating_factor)
    available = producer.baseline_supply_bbl_week * effective_supply
    scarcity = max(0.0, 1.0 - effective_supply) * 18.0
    fear_markup = (locality.fear_multiplier - 1.0) * (11.0 + producer.risk_weight * 4.0)
    inventory_pressure = max(
        0.0,
        1.0 - _safe_div(world.crude_inventory[producer.locality], locality.baseline_refinery_throughput_bbl_week * 1.4),
    )
    operating_risk = _stable_noise(config.seed, world.week, f"ask:{producer.id}") * (1.2 + producer.risk_weight * 4.0)
    ask = producer.cost_floor_per_bbl + scarcity + fear_markup + inventory_pressure * 6.5 + operating_risk
    return available, max(24.0, ask)


def _refinery_target_need(
    refinery: RefineryAgent,
    world: WorldState,
    policy: PolicyControls,
    config: SimulationConfig,
    scenario: ScenarioPreset,
) -> tuple[float, float, float]:
    shock = scenario.refinery_capacity_shocks.get(refinery.locality, 1.0)
    shock *= scenario.refinery_country_shocks.get(refinery.country, 1.0)
    subsidy_boost = 1.0 + policy.refinery_subsidy_pct * 0.45
    local_prices = world.last_product_prices[refinery.locality]
    expected_basket_value = sum(
        refinery.yield_shares[product] * max(BASE_PRODUCT_PRICES[product], local_prices[product])
        for product in PRODUCTS
    )
    processing_cost = refinery.processing_cost_per_bbl * (1.0 - policy.refinery_subsidy_pct)
    expected_crude_cost = world.last_crude_price_by_locality[refinery.locality]
    expected_margin = expected_basket_value - processing_cost - expected_crude_cost
    margin_signal = _clamp((expected_margin - 6.0) / 24.0, -0.42, 0.34)
    target_utilization = _clamp(refinery.baseline_utilization + margin_signal, 0.18, 0.98)
    target_utilization = _clamp(target_utilization * shock * subsidy_boost, 0.12, 1.02)
    operating_factor = 1.0 + _stable_noise(config.seed, world.week, f"refinery:{refinery.id}") * 0.030
    target_throughput = refinery.weekly_crude_capacity_bbl * target_utilization * operating_factor
    desired_margin = max(4.0, 7.0 - min(2.0, refinery.complexity_score * 0.10))
    willingness_to_pay = max(30.0, expected_basket_value - processing_cost - desired_margin)
    return target_throughput, processing_cost, willingness_to_pay


def _product_ask_price(world: WorldState, locality_id: str, product: str, available_bbl: float) -> float:
    locality = world.localities[locality_id]
    base_demand = locality.base_product_demand_bbl_week[product]
    coverage = _safe_div(available_bbl, base_demand)
    inventory_cost = world.product_cost_basis[locality_id][product]
    replacement_cost = (
        world.last_crude_price_by_locality[locality_id] * PRODUCT_CRUDE_PASS_THROUGH[product]
        + PRODUCT_CONVERSION_PREMIUM[product]
        + PRODUCT_TARGET_MARGIN[product]
    )
    cost_floor = max(BASE_PRODUCT_PRICES[product] * 0.55, inventory_cost, replacement_cost)
    scarcity_markup = 1.0 + max(0.0, 0.95 - coverage) * 0.58
    fear_markup = 1.0 + max(0.0, locality.fear_multiplier - 1.0) * 0.24
    return cost_floor * scarcity_markup * fear_markup


def _military_conflict_demand_multiplier(agent: DemandAgent, product: str, scenario: ScenarioPreset) -> float:
    if agent.agent_kind != "military":
        return 1.0
    direct_shock = scenario.military_demand_shocks.get(agent.locality, 0.0)
    fear_shock = scenario.locality_fear_shocks.get(agent.locality, 0.0)
    response = MILITARY_CONFLICT_DEMAND_RESPONSE[product]
    return 1.0 + max(0.0, direct_shock) + max(0.0, fear_shock) * response


def _military_conflict_bid_multiplier(agent: DemandAgent, product: str, scenario: ScenarioPreset) -> float:
    if agent.agent_kind != "military":
        return 1.0
    direct_shock = scenario.military_demand_shocks.get(agent.locality, 0.0)
    fear_shock = scenario.locality_fear_shocks.get(agent.locality, 0.0)
    response = MILITARY_CONFLICT_BID_RESPONSE[product]
    return 1.0 + max(0.0, direct_shock) * 0.65 + max(0.0, fear_shock) * response


def _military_strategy_demand_multiplier(agent: DemandAgent, product: str, strategy: MilitaryStrategyPreset) -> float:
    if agent.agent_kind != "military":
        return 1.0
    product_multiplier = max(0.0, strategy.product_demand_multipliers.get(product, 1.0))
    locality_multiplier = 1.0 + max(0.0, strategy.locality_demand_shocks.get(agent.locality, 0.0))
    return product_multiplier * locality_multiplier


def _military_strategy_bid_multiplier(agent: DemandAgent, product: str, strategy: MilitaryStrategyPreset) -> float:
    if agent.agent_kind != "military":
        return 1.0
    return max(0.0, strategy.product_bid_multipliers.get(product, 1.0))


def _demand_for_agent(
    agent: DemandAgent,
    world: WorldState,
    policy: PolicyControls,
    config: SimulationConfig,
    scenario: ScenarioPreset,
    strategy: MilitaryStrategyPreset,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    locality = world.localities[agent.locality]
    demand: dict[str, float] = {}
    bids: dict[str, float] = {}
    latent_demand: dict[str, float] = {}
    for product in PRODUCTS:
        base = agent.base_demand_bbl_week[product]
        backlog_ratio = _safe_div(agent.backlog_bbl[product], max(base, 1.0))
        price_ratio = _clamp(world.last_product_prices[agent.locality][product] / BASE_PRODUCT_PRICES[product], 0.55, 3.50)
        elasticity = _segment_elasticity(agent, product)
        seasonal = _seasonal_multiplier(world.week, product, agent.segment)
        demand_noise = 1.0 + _stable_noise(config.seed, world.week, f"demand:{agent.id}:{product}") * 0.025
        price_response = _clamp(price_ratio**elasticity, 0.68, 1.18)
        if agent.agent_kind == "military":
            panic_sensitivity = 0.04
        elif agent.agent_kind == "household":
            panic_sensitivity = 0.08
        else:
            panic_sensitivity = 0.22
        if agent.agent_kind != "military" and (
            (agent.segment, product) in STRATEGIC_PRODUCTS or agent.segment in {"heavy_logistics", "aviation"}
        ):
            panic_sensitivity = 0.38
        panic_stocking = 1.0 + max(0.0, locality.fear_multiplier - 1.0) * panic_sensitivity
        backlog_multiplier = 1.0 + min(0.45, backlog_ratio * config.demand_sensitivity)
        conflict_multiplier = _military_conflict_demand_multiplier(agent, product, scenario)
        strategy_demand_multiplier = _military_strategy_demand_multiplier(agent, product, strategy)
        unconstrained_quantity = (
            base
            * seasonal
            * demand_noise
            * panic_stocking
            * backlog_multiplier
            * conflict_multiplier
            * strategy_demand_multiplier
        )
        quantity = unconstrained_quantity * price_response
        demand[product] = quantity
        rationing_weight = _clamp(0.18 + max(0.0, locality.fear_multiplier - 1.0) * 0.20, 0.18, 0.70)
        latent_demand[product] = quantity + max(0.0, unconstrained_quantity - quantity) * rationing_weight
        priority = agent.price_priority[product]
        strategic_boost = 0.0
        if (agent.segment, product) in STRATEGIC_PRODUCTS:
            strategic_boost = policy.military_priority_pct
        price_anchor = max(BASE_PRODUCT_PRICES[product], world.last_product_prices[agent.locality][product])
        bids[product] = (
            price_anchor
            * priority
            * agent.income_multiplier
            * locality.fear_multiplier
            * (1.0 + strategic_boost)
            * _military_conflict_bid_multiplier(agent, product, scenario)
            * _military_strategy_bid_multiplier(agent, product, strategy)
            * (1.0 + min(0.10, backlog_ratio * 0.05))
        )
        if agent.agent_kind == "military":
            military_bid_floor = (
                BASE_PRODUCT_PRICES[product]
                * MILITARY_MIN_BID_MULTIPLIER[product]
                * (1.0 + policy.military_priority_pct)
                * _military_conflict_bid_multiplier(agent, product, scenario)
                * _military_strategy_bid_multiplier(agent, product, strategy)
            )
            bids[product] = max(bids[product], military_bid_floor)
    return demand, bids, latent_demand


def _clear_crude_auction(
    world: WorldState,
    config: SimulationConfig,
    scenario: ScenarioPreset,
    effective_routes: dict[tuple[str, str], RouteState],
    procurement_requests: list[dict[str, Any]],
    route_remaining_capacity: dict[tuple[str, str], float],
) -> tuple[dict[str, list[tuple[float, float]]], dict[str, list[float]]]:
    sell_tranches: list[dict[str, Any]] = []
    for producer in world.producers:
        available, ask = _producer_supply_offer(producer, world, config, scenario)
        for tranche_index, (share, premium) in enumerate(CRUDE_SUPPLY_TRANCHES):
            volume = available * share
            if volume <= 1.0:
                continue
            sell_tranches.append(
                {
                    "producer": producer,
                    "remaining": volume,
                    "ask": ask + premium,
                    "tranche_index": tranche_index,
                }
            )

    buy_tranches: list[dict[str, Any]] = []
    for request in procurement_requests:
        requested = request["remaining_need"]
        if requested <= 1.0:
            continue
        for tranche_index, (share, bid_multiplier) in enumerate(CRUDE_DEMAND_TRANCHES):
            volume = requested * share
            if volume <= 1.0:
                continue
            buy_tranches.append(
                {
                    "refinery": request["refinery"],
                    "remaining": volume,
                    "bid": request["mwtp"] * bid_multiplier,
                    "tranche_index": tranche_index,
                }
            )

    buy_tranches.sort(key=lambda item: item["bid"], reverse=True)
    matches: list[dict[str, Any]] = []
    crude_rejected_bids: dict[str, list[float]] = defaultdict(list)

    for buy in buy_tranches:
        refinery = buy["refinery"]
        while buy["remaining"] > 1.0:
            candidates: list[tuple[float, dict[str, Any], RouteState]] = []
            for sell in sell_tranches:
                if sell["remaining"] <= 1.0:
                    continue
                producer = sell["producer"]
                origin = producer.locality
                destination = refinery.locality
                if _is_country_locality_crude_embargoed(producer, refinery):
                    continue
                route = effective_routes[(origin, destination)]
                key = (origin, destination)
                capacity_left = route_remaining_capacity[key]
                if route.blocked or capacity_left <= 1.0:
                    continue
                delivered_ask = sell["ask"] + route.shipping_cost_per_bbl
                if delivered_ask > buy["bid"]:
                    continue
                candidates.append((delivered_ask, sell, route))

            if not candidates:
                break

            candidates.sort(key=lambda item: item[0])
            delivered_ask, sell, route = candidates[0]
            producer = sell["producer"]
            key = (producer.locality, refinery.locality)
            volume = min(buy["remaining"], sell["remaining"], route_remaining_capacity[key])
            if volume <= 1.0:
                break
            route_remaining_capacity[key] -= volume
            sell["remaining"] -= volume
            buy["remaining"] -= volume
            matches.append(
                {
                    "destination": refinery.locality,
                    "origin": producer.locality,
                    "volume": volume,
                    "delivered_ask": delivered_ask,
                    "bid": buy["bid"],
                    "route": route,
                    "producer_id": producer.id,
                    "refinery_id": refinery.id,
                }
            )

        if buy["remaining"] > 1.0:
            crude_rejected_bids[refinery.locality].append(buy["bid"])

    crude_trades: dict[str, list[tuple[float, float]]] = defaultdict(list)
    matches_by_destination: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        matches_by_destination[match["destination"]].append(match)

    for destination, destination_matches in matches_by_destination.items():
        marginal_ask = max(match["delivered_ask"] for match in destination_matches)
        marginal_bid = min(match["bid"] for match in destination_matches)
        rejected_bid = max(crude_rejected_bids.get(destination, []), default=0.0)
        rejected_pressure = max(0.0, rejected_bid - marginal_ask) * 0.25
        clearing_price = min(marginal_bid, marginal_ask + rejected_pressure)
        for match in destination_matches:
            volume = match["volume"]
            route = match["route"]
            crude_trades[destination].append((volume, clearing_price))
            if route.latency_weeks == 0:
                world.crude_inventory[destination] += volume
            else:
                world.shipments_in_transit.append(
                    Shipment(
                        origin=match["origin"],
                        destination=destination,
                        volume_bbl=volume,
                        arrival_week=world.week + route.latency_weeks,
                        unit_cost_per_bbl=clearing_price,
                        supplier_id=match["producer_id"],
                        buyer_id=match["refinery_id"],
                        commodity="crude",
                    )
                )

    return crude_trades, crude_rejected_bids


def _next_backlog_bbl(
    agent: DemandAgent,
    product: str,
    scenario: ScenarioPreset,
    demand_bbl: float,
    fulfilled_bbl: float,
    unmet_bbl: float,
) -> float:
    base = agent.base_demand_bbl_week[product]
    if base <= 0.0:
        return 0.0
    fulfillment = _safe_div(fulfilled_bbl, demand_bbl)
    if fulfillment >= 0.96:
        next_backlog = agent.backlog_bbl[product] * 0.18
    elif fulfillment >= 0.88:
        next_backlog = agent.backlog_bbl[product] * 0.35 + unmet_bbl * 0.25
    else:
        next_backlog = agent.backlog_bbl[product] * 0.42 + unmet_bbl * 0.45
    cap_multiplier = 0.45 if _is_baseline_scenario(scenario) else 1.8
    return min(base * cap_multiplier, next_backlog)


def _local_product_reserve_share(agent: DemandAgent, scenario: ScenarioPreset) -> float:
    if agent.agent_kind == "military":
        return MILITARY_LOCAL_PRODUCT_RESERVE_SHARE
    if _is_baseline_scenario(scenario):
        return BASELINE_LOCAL_PRODUCT_RESERVE_SHARE
    return STRESSED_LOCAL_PRODUCT_RESERVE_SHARE


def _apply_baseline_commercial_balancing(
    scenario: ScenarioPreset,
    demand_by_locality_product: dict[str, dict[str, float]],
    fulfilled_by_locality_product: dict[str, dict[str, float]],
    unmet_by_locality_product: dict[str, dict[str, float]],
    agent_product_outcomes: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> None:
    if not _is_baseline_scenario(scenario):
        return
    for locality_id, product_demands in demand_by_locality_product.items():
        for product, demand in product_demands.items():
            if demand <= 0.0:
                continue
            max_unmet = demand * BASELINE_COMMERCIAL_MAX_SHORTAGE[product]
            unmet = unmet_by_locality_product[locality_id][product]
            if unmet <= max_unmet:
                continue
            balanced_volume = unmet - max_unmet
            unmet_by_locality_product[locality_id][product] = max_unmet
            fulfilled_by_locality_product[locality_id][product] += balanced_volume
            if agent_product_outcomes is not None:
                _rebalance_agent_product_outcomes(agent_product_outcomes, locality_id, product, balanced_volume)


def _rebalance_agent_product_outcomes(
    agent_product_outcomes: dict[tuple[str, str], dict[str, Any]],
    locality_id: str,
    product: str,
    balanced_volume_bbl: float,
) -> None:
    if balanced_volume_bbl <= 0.0:
        return
    candidates = [
        outcome
        for (_, outcome_product), outcome in agent_product_outcomes.items()
        if outcome_product == product
        and outcome["locality"] == locality_id
        and float(outcome["unmet_bbl"]) > 0.0
    ]
    total_unmet = sum(float(outcome["unmet_bbl"]) for outcome in candidates)
    if total_unmet <= 0.0:
        return
    for outcome in candidates:
        unmet = float(outcome["unmet_bbl"])
        adjustment = min(unmet, balanced_volume_bbl * unmet / total_unmet)
        outcome["unmet_bbl"] = max(0.0, unmet - adjustment)
        outcome["fulfilled_bbl"] = float(outcome["fulfilled_bbl"]) + adjustment


def _clear_product_auction(
    world: WorldState,
    config: SimulationConfig,
    policy: PolicyControls,
    scenario: ScenarioPreset,
    strategy: MilitaryStrategyPreset,
    effective_routes: dict[tuple[str, str], RouteState],
    demand_by_locality_product: dict[str, dict[str, float]],
    fulfilled_by_locality_product: dict[str, dict[str, float]],
    unmet_by_locality_product: dict[str, dict[str, float]],
) -> ProductAuctionResult:
    product_trades: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    military_demand_by_product = {product: 0.0 for product in PRODUCTS}
    military_fulfilled_by_product = {product: 0.0 for product in PRODUCTS}
    agent_product_outcomes: dict[tuple[str, str], dict[str, Any]] = {}

    for product in PRODUCTS:
        product_route_remaining_capacity = {
            key: route.base_capacity_bbl * route.capacity_multiplier * PRODUCT_ROUTE_CAPACITY_SHARE
            for key, route in effective_routes.items()
        }
        source_asks = {
            locality_id: _product_ask_price(world, locality_id, product, world.product_inventory[locality_id][product])
            for locality_id in world.localities
        }
        delivered_floor_by_destination: dict[str, float] = {}
        for destination in world.localities:
            delivered_options: list[float] = []
            for source_locality in world.localities:
                if world.product_inventory[source_locality][product] <= 1.0:
                    continue
                route = effective_routes[(source_locality, destination)]
                key = (source_locality, destination)
                if route.blocked or product_route_remaining_capacity[key] <= 1.0:
                    continue
                delivered_options.append(source_asks[source_locality] + route.shipping_cost_per_bbl * 0.72)
            delivered_floor_by_destination[destination] = min(
                delivered_options,
                default=source_asks[destination],
            )
        sell_tranches: list[dict[str, Any]] = []
        for source_locality in world.localities:
            available = world.product_inventory[source_locality][product]
            if available <= 1.0:
                continue
            for tranche_index, (share, ask_multiplier) in enumerate(PRODUCT_SUPPLY_TRANCHES):
                volume = available * share
                if volume <= 1.0:
                    continue
                sell_tranches.append(
                    {
                        "source": source_locality,
                        "remaining": volume,
                        "ask": source_asks[source_locality] * ask_multiplier,
                        "tranche_index": tranche_index,
                    }
                )

        buy_tranches: list[dict[str, Any]] = []
        demand_trackers: dict[tuple[str, str], dict[str, Any]] = {}
        for agent in world.demand_agents:
            quantities, bids, latent_quantities = _demand_for_agent(agent, world, policy, config, scenario, strategy)
            demand = quantities[product]
            latent_demand = latent_quantities[product]
            bid = bids[product]
            if latent_demand <= 1.0 and demand <= 1.0:
                continue
            tracker_key = (agent.id, product)
            tranche_entries: list[dict[str, Any]] = []
            orderable_demand = 0.0
            if demand <= 1.0:
                continue
            delivered_floor = delivered_floor_by_destination[agent.locality]
            for tranche_index, (share, bid_multiplier) in enumerate(PRODUCT_DEMAND_TRANCHES):
                volume = demand * share
                if volume <= 1.0:
                    continue
                tranche_bid = bid * bid_multiplier
                if tranche_bid < delivered_floor * PRODUCT_ORDER_BID_FLOOR_MULTIPLIER:
                    continue
                orderable_demand += volume
                tranche_entries.append(
                    {
                        "agent": agent,
                        "remaining": volume,
                        "bid": tranche_bid,
                        "tracker_key": tracker_key,
                        "tranche_index": tranche_index,
                    }
                )
            if orderable_demand <= 1.0:
                continue
            demand_trackers[tracker_key] = {
                "agent": agent,
                "demand": orderable_demand,
                "latent_demand": latent_demand,
                "fulfilled": 0.0,
            }
            demand_by_locality_product[agent.locality][product] += orderable_demand
            for entry in tranche_entries:
                buy_tranches.append(
                    entry
                )

        buy_tranches.sort(
            key=lambda item: (item["agent"].agent_kind == "military", item["bid"]),
            reverse=True,
        )
        for buy in buy_tranches:
            agent = buy["agent"]
            destination = agent.locality
            while buy["remaining"] > 1.0:
                candidates: list[tuple[float, dict[str, Any], RouteState]] = []
                for sell in sell_tranches:
                    if sell["remaining"] <= 1.0:
                        continue
                    source_locality = sell["source"]
                    route = effective_routes[(source_locality, destination)]
                    key = (source_locality, destination)
                    capacity_left = product_route_remaining_capacity[key]
                    if route.blocked or capacity_left <= 1.0:
                        continue
                    available_for_order = world.product_inventory[source_locality][product]
                    if source_locality != destination:
                        local_reserve_share = _local_product_reserve_share(agent, scenario)
                        local_reserve = demand_by_locality_product[source_locality][product] * local_reserve_share
                        local_need_remaining = max(
                            0.0,
                            local_reserve - fulfilled_by_locality_product[source_locality][product],
                        )
                        available_for_order = max(0.0, available_for_order - local_need_remaining)
                        if available_for_order <= 1.0:
                            continue
                    delivered_cost = sell["ask"] + route.shipping_cost_per_bbl * 0.72
                    if delivered_cost > buy["bid"]:
                        continue
                    candidates.append((delivered_cost, sell, route))

                if not candidates:
                    break

                candidates.sort(key=lambda item: item[0])
                delivered_cost, sell, route = candidates[0]
                source_locality = sell["source"]
                key = (source_locality, destination)
                volume = min(
                    buy["remaining"],
                    sell["remaining"],
                    product_route_remaining_capacity[key],
                    world.product_inventory[source_locality][product],
                )
                if source_locality != destination:
                    local_reserve_share = _local_product_reserve_share(agent, scenario)
                    local_reserve = demand_by_locality_product[source_locality][product] * local_reserve_share
                    local_need_remaining = max(
                        0.0,
                        local_reserve - fulfilled_by_locality_product[source_locality][product],
                    )
                    volume = min(volume, max(0.0, world.product_inventory[source_locality][product] - local_need_remaining))
                if volume <= 1.0:
                    sell["remaining"] = 0.0
                    break
                drawn = _draw_product_inventory(world, source_locality, product, volume)
                if drawn <= 1.0:
                    sell["remaining"] = 0.0
                    break
                product_route_remaining_capacity[key] -= drawn
                sell["remaining"] -= drawn
                buy["remaining"] -= drawn
                product_trades[(destination, product)].append((drawn, delivered_cost))
                credited_volume = drawn * _in_transit_service_credit(route.latency_weeks)
                fulfilled_by_locality_product[destination][product] += credited_volume
                demand_trackers[buy["tracker_key"]]["fulfilled"] += credited_volume
                if route.latency_weeks > 0:
                    world.shipments_in_transit.append(
                        Shipment(
                            origin=source_locality,
                            destination=destination,
                            volume_bbl=drawn,
                            arrival_week=world.week + route.latency_weeks,
                            unit_cost_per_bbl=delivered_cost,
                            supplier_id=f"{source_locality}:{product}",
                            buyer_id=agent.id,
                            commodity=product,
                        )
                    )

        for tracker in demand_trackers.values():
            agent = tracker["agent"]
            demand = tracker["demand"]
            fulfilled = tracker["fulfilled"]
            unmet = max(0.0, demand - fulfilled)
            if agent.agent_kind == "military":
                military_demand_by_product[product] += demand
                military_fulfilled_by_product[product] += fulfilled
            unmet_by_locality_product[agent.locality][product] += unmet
            agent_product_outcomes[(agent.id, product)] = {
                "locality": agent.locality,
                "agent_kind": agent.agent_kind,
                "segment": agent.segment,
                "income_multiplier": agent.income_multiplier,
                "demand_bbl": demand,
                "fulfilled_bbl": fulfilled,
                "unmet_bbl": unmet,
                "latent_demand_bbl": tracker["latent_demand"],
            }
            agent.backlog_bbl[product] = _next_backlog_bbl(
                agent,
                product,
                scenario,
                demand,
                fulfilled,
                unmet,
            )

    return ProductAuctionResult(
        trades=product_trades,
        military_demand_by_product=military_demand_by_product,
        military_fulfilled_by_product=military_fulfilled_by_product,
        agent_product_outcomes=agent_product_outcomes,
    )


def _empty_household_bucket() -> dict[str, float]:
    return {"baseline_cost": 0.0, "current_cost": 0.0, "demand_bbl": 0.0, "fulfilled_bbl": 0.0}


def _empty_industrial_bucket() -> dict[str, float]:
    return {
        "weighted_demand_bbl": 0.0,
        "weighted_fulfilled_bbl": 0.0,
        "weighted_unmet_bbl": 0.0,
        "weighted_price_drag_bbl": 0.0,
    }


def _calculate_economic_indicators(
    product_prices: dict[str, dict[str, float]],
    agent_product_outcomes: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    household_buckets: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(_empty_household_bucket)
    )
    industrial_buckets: dict[str, dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(_empty_industrial_bucket)
    )

    for (_, product), outcome in agent_product_outcomes.items():
        locality_id = str(outcome["locality"])
        agent_kind = str(outcome["agent_kind"])
        segment = str(outcome["segment"])
        demand_bbl = float(outcome["demand_bbl"])
        fulfilled_bbl = float(outcome["fulfilled_bbl"])
        unmet_bbl = float(outcome["unmet_bbl"])
        if demand_bbl <= 0.0:
            continue
        price = product_prices.get(locality_id, {}).get(product, BASE_PRODUCT_PRICES[product])

        if agent_kind == "household":
            income_multiplier = max(0.20, float(outcome.get("income_multiplier", 1.0)))
            segment_weight = HOUSEHOLD_AFFORDABILITY_SEGMENT_WEIGHTS.get(segment, 1.0) / income_multiplier
            for bucket_name in (segment, "overall"):
                bucket = household_buckets[locality_id][bucket_name]
                bucket["baseline_cost"] += BASE_PRODUCT_PRICES[product] * demand_bbl * segment_weight
                bucket["current_cost"] += price * demand_bbl * segment_weight
                bucket["demand_bbl"] += demand_bbl * segment_weight
                bucket["fulfilled_bbl"] += fulfilled_bbl * segment_weight

        if agent_kind == "sector":
            criticality = INDUSTRIAL_PRODUCT_CRITICALITY.get(segment, {}).get(product, 0.0)
            if criticality <= 0.0:
                continue
            segment_weight = INDUSTRIAL_SEGMENT_OUTPUT_WEIGHTS.get(segment, 1.0)
            weighted_demand = demand_bbl * criticality * segment_weight
            weighted_fulfilled = fulfilled_bbl * criticality * segment_weight
            weighted_unmet = unmet_bbl * criticality * segment_weight
            price_ratio = price / max(1.0, BASE_PRODUCT_PRICES[product])
            weighted_price_drag = (
                fulfilled_bbl
                * criticality
                * segment_weight
                * max(0.0, price_ratio - 1.0)
                * INDUSTRIAL_PRICE_DRAG_FACTOR
            )
            for bucket_name in (segment, "overall"):
                bucket = industrial_buckets[locality_id][bucket_name]
                bucket["weighted_demand_bbl"] += weighted_demand
                bucket["weighted_fulfilled_bbl"] += weighted_fulfilled
                bucket["weighted_unmet_bbl"] += weighted_unmet
                bucket["weighted_price_drag_bbl"] += weighted_price_drag

    household_scores = {
        locality_id: {
            "overall": 100.0,
            "price_burden_ratio": 1.0,
            "fulfillment_ratio": 1.0,
            **{quartile: 100.0 for quartile in HOUSEHOLD_QUARTILES},
        }
        for locality_id in product_prices
    }
    for locality_id, locality_buckets in household_buckets.items():
        household_scores.setdefault(
            locality_id,
            {
                "overall": 100.0,
                "price_burden_ratio": 1.0,
                "fulfillment_ratio": 1.0,
                **{quartile: 100.0 for quartile in HOUSEHOLD_QUARTILES},
            },
        )
        for bucket_name, bucket in locality_buckets.items():
            price_burden = _safe_div(bucket["current_cost"], bucket["baseline_cost"])
            fulfillment = _safe_div(bucket["fulfilled_bbl"], bucket["demand_bbl"])
            affordability = _clamp(100.0 * fulfillment / max(price_burden, 0.01), 0.0, 125.0)
            household_scores[locality_id][bucket_name] = affordability
            if bucket_name == "overall":
                household_scores[locality_id]["price_burden_ratio"] = price_burden
                household_scores[locality_id]["fulfillment_ratio"] = fulfillment

    industrial_scores = {
        locality_id: {
            "overall": 0.0,
            "shortage_component": 0.0,
            "price_component": 0.0,
            **{sector: 0.0 for sector in SECTORS},
            **{f"{sector}_shortage_component": 0.0 for sector in SECTORS},
            **{f"{sector}_price_component": 0.0 for sector in SECTORS},
        }
        for locality_id in product_prices
    }
    industrial_output_scores = {
        locality_id: {
            "overall": 100.0,
            "oil_input_ratio": 1.0,
            "input_weight_bbl": 0.0,
            **{sector: 100.0 for sector in SECTORS},
            **{f"{sector}_oil_input_ratio": 1.0 for sector in SECTORS},
            **{f"{sector}_input_weight_bbl": 0.0 for sector in SECTORS},
        }
        for locality_id in product_prices
    }
    for locality_id, locality_buckets in industrial_buckets.items():
        industrial_scores.setdefault(
            locality_id,
            {
                "overall": 0.0,
                "shortage_component": 0.0,
                "price_component": 0.0,
                **{sector: 0.0 for sector in SECTORS},
                **{f"{sector}_shortage_component": 0.0 for sector in SECTORS},
                **{f"{sector}_price_component": 0.0 for sector in SECTORS},
            },
        )
        industrial_output_scores.setdefault(
            locality_id,
            {
                "overall": 100.0,
                "oil_input_ratio": 1.0,
                "input_weight_bbl": 0.0,
                **{sector: 100.0 for sector in SECTORS},
                **{f"{sector}_oil_input_ratio": 1.0 for sector in SECTORS},
                **{f"{sector}_input_weight_bbl": 0.0 for sector in SECTORS},
            },
        )
        for bucket_name, bucket in locality_buckets.items():
            shortage_component = _clamp(
                _safe_div(bucket["weighted_unmet_bbl"], bucket["weighted_demand_bbl"]),
                0.0,
                1.0,
            )
            oil_input_ratio = _clamp(
                _safe_div(bucket["weighted_fulfilled_bbl"], bucket["weighted_demand_bbl"]),
                0.0,
                1.0,
            )
            price_component = _clamp(
                _safe_div(bucket["weighted_price_drag_bbl"], bucket["weighted_demand_bbl"]),
                0.0,
                max(0.0, 1.0 - shortage_component),
            )
            output_at_risk = shortage_component + price_component
            output_index = _industrial_economic_output_index(oil_input_ratio, output_at_risk)
            if bucket_name == "overall":
                industrial_scores[locality_id]["overall"] = output_at_risk
                industrial_scores[locality_id]["shortage_component"] = shortage_component
                industrial_scores[locality_id]["price_component"] = price_component
                industrial_output_scores[locality_id]["overall"] = output_index
                industrial_output_scores[locality_id]["oil_input_ratio"] = oil_input_ratio
                industrial_output_scores[locality_id]["input_weight_bbl"] = bucket["weighted_demand_bbl"]
            else:
                industrial_scores[locality_id][bucket_name] = output_at_risk
                industrial_scores[locality_id][f"{bucket_name}_shortage_component"] = shortage_component
                industrial_scores[locality_id][f"{bucket_name}_price_component"] = price_component
                industrial_output_scores[locality_id][bucket_name] = output_index
                industrial_output_scores[locality_id][f"{bucket_name}_oil_input_ratio"] = oil_input_ratio
                industrial_output_scores[locality_id][f"{bucket_name}_input_weight_bbl"] = bucket["weighted_demand_bbl"]

    return household_scores, industrial_scores, industrial_output_scores


def _generate_events(
    world: WorldState,
    step: StepResult,
    scenario: ScenarioPreset,
    reserve_operation: ReserveOperationResult,
    blocked_routes: list[tuple[str, str]],
    crude_trades: dict[str, list[tuple[float, float]]],
    crude_rejected_bids: dict[str, list[float]],
    previous_crude_prices: dict[str, float],
    previous_shortage_ratio: dict[str, float],
) -> list[str]:
    events: list[str] = []
    if blocked_routes and not _is_baseline_scenario(scenario):
        origin, destination = blocked_routes[0]
        events.append(
            f"Route pressure: {len(blocked_routes)} directed lanes are blocked; {world.localities[origin].label} -> {world.localities[destination].label} is forcing cargo onto longer lanes."
        )

    highest_fear_locality = max(world.localities, key=lambda locality_id: world.localities[locality_id].fear_multiplier)
    highest_fear = world.localities[highest_fear_locality].fear_multiplier
    if highest_fear > 1.05:
        scenario_fear = scenario.locality_fear_shocks.get(highest_fear_locality, 0.0)
        fear_driver = f"a {scenario_fear:.0%} scenario shock" if scenario_fear > 0.0 else "local shortage pressure"
        events.append(
            f"Panic signal: {world.localities[highest_fear_locality].label} fear is {highest_fear:.2f}x after {fear_driver}, lifting bids and asks."
        )

    rejected_markets = {
        locality_id: max(bids)
        for locality_id, bids in crude_rejected_bids.items()
        if bids
    }
    if rejected_markets:
        rejected_locality = max(rejected_markets, key=rejected_markets.get)
        events.append(
            f"Auction stress: {world.localities[rejected_locality].label} rejected crude bids up to ${rejected_markets[rejected_locality]:.0f}/bbl after shipping and route filters."
        )

    most_stressed = sorted(step.locality_shortage_ratio.items(), key=lambda item: item[1], reverse=True)
    shortage_event_threshold = 0.12 if _is_baseline_scenario(scenario) else 0.05
    if most_stressed and most_stressed[0][1] > shortage_event_threshold:
        locality_id, shortage = most_stressed[0]
        worst_product = max(
            PRODUCTS,
            key=lambda product: step.unmet_demand_by_locality_product[locality_id][product],
        )
        previous = previous_shortage_ratio.get(locality_id, 0.0)
        events.append(
            f"Market clearing: {world.localities[locality_id].label} shortage is {shortage:.0%} ({shortage - previous:+.0%} WoW), led by {worst_product} stress."
        )

    if reserve_operation.returned_bbl > 0.0:
        events.append(
            f"SPR refill: exchange returns add {reserve_operation.returned_bbl / 1_000_000:.2f}M bbl back into the reserve."
        )

    if reserve_operation.distribution:
        biggest_locality = max(reserve_operation.distribution, key=reserve_operation.distribution.get)
        release_label = "sale" if reserve_operation.release_mode == "sale" else "exchange"
        events.append(
            f"Policy response: SPR {release_label} releases {reserve_operation.released_bbl / 1_000_000:.2f}M bbl, led by {reserve_operation.distribution[biggest_locality] / 1_000_000:.2f}M bbl to {world.localities[biggest_locality].label}."
        )

    if reserve_operation.purchased_bbl > 0.0:
        events.append(
            f"SPR purchase: DOE buys {reserve_operation.purchased_bbl / 1_000_000:.2f}M bbl for refill at modeled market prices."
        )

    price_moves = {
        locality_id: step.crude_price_by_locality[locality_id] - previous_crude_prices.get(locality_id, step.crude_price_by_locality[locality_id])
        for locality_id in step.crude_price_by_locality
    }
    if price_moves:
        spiking_locality = max(price_moves, key=price_moves.get)
        price_delta = price_moves[spiking_locality]
        observed_price = step.crude_price_by_locality[spiking_locality]
        if price_delta > 3.0:
            events.append(
                f"Crude repricing: {world.localities[spiking_locality].label} moved +${price_delta:.0f}/bbl to ${observed_price:.0f}/bbl."
            )

    if scenario.name != "Baseline" and len(events) < 3:
        events.append(f"Scenario pressure remains active: {scenario.description}")

    return events[:5]


def step_world(
    world: WorldState,
    config: SimulationConfig,
    scenarios: dict[str, ScenarioPreset],
    military_strategies: dict[str, MilitaryStrategyPreset] | None = None,
) -> StepResult:
    scenario = scenarios[config.selected_scenario]
    strategy = _select_military_strategy(config, military_strategies)
    policy = _effective_policy(config, scenario)
    previous_crude_prices = dict(world.last_crude_price_by_locality)
    previous_shortage_ratio = dict(world.history[-1].locality_shortage_ratio) if world.history else {}

    world.week += 1
    _resolve_arrivals(world)
    effective_routes = _effective_routes(world, config, scenario, policy)
    blocked_routes = [
        key
        for key, route in effective_routes.items()
        if key[0] != key[1] and route.blocked and route.base_capacity_bbl > 0.0
    ]
    reserve_operation = _apply_reserve_policy(world, policy)
    _pre_clear_locality_fear(world, scenario)

    locality_refiners: dict[str, list[RefineryAgent]] = defaultdict(list)
    for refinery in world.refiners:
        locality_refiners[refinery.locality].append(refinery)

    locality_capacity_totals = {
        locality_id: sum(refinery.weekly_crude_capacity_bbl for refinery in refiners)
        for locality_id, refiners in locality_refiners.items()
    }

    refinery_targets: dict[str, float] = {}
    refinery_mwtp: dict[str, float] = {}
    refinery_processing_costs: dict[str, float] = {}
    procurement_requests: list[dict[str, Any]] = []

    for refinery in world.refiners:
        target_throughput, processing_cost, willingness_to_pay = _refinery_target_need(refinery, world, policy, config, scenario)
        locality_inventory = world.crude_inventory[refinery.locality]
        locality_total_capacity = max(1.0, locality_capacity_totals.get(refinery.locality, refinery.weekly_crude_capacity_bbl))
        inventory_share = locality_inventory * refinery.weekly_crude_capacity_bbl / locality_total_capacity
        desired_cover = target_throughput * config.inventory_cover_weeks
        request_volume = max(0.0, desired_cover - inventory_share)
        refinery_targets[refinery.id] = target_throughput
        refinery_mwtp[refinery.id] = willingness_to_pay
        refinery_processing_costs[refinery.id] = processing_cost
        procurement_requests.append(
            {
                "mwtp": willingness_to_pay,
                "refinery_id": refinery.id,
                "refinery": refinery,
                "remaining_need": request_volume,
            }
        )

    procurement_requests.sort(key=lambda item: item["mwtp"], reverse=True)
    route_remaining_capacity = {
        key: route.base_capacity_bbl * route.capacity_multiplier for key, route in effective_routes.items()
    }
    crude_trades, crude_rejected_bids = _clear_crude_auction(
        world,
        config,
        scenario,
        effective_routes,
        procurement_requests,
        route_remaining_capacity,
    )

    refinery_utilization: dict[str, float] = {}
    for locality_id, refiners in locality_refiners.items():
        available_crude = world.crude_inventory[locality_id]
        total_target = sum(refinery_targets[refinery.id] for refinery in refiners)
        if total_target <= 0 or available_crude <= 0:
            for refinery in refiners:
                refinery_utilization[refinery.id] = 0.0
            continue
        fill_ratio = min(1.0, available_crude / total_target)
        consumed = 0.0
        for refinery in refiners:
            processed = refinery_targets[refinery.id] * fill_ratio
            consumed += processed
            refinery_utilization[refinery.id] = _safe_div(processed, max(refinery.weekly_crude_capacity_bbl, 1.0))
            efficiency_boost = 1.0 + max(0.0, refinery.complexity_score - 8.0) * 0.004
            crude_feedstock_cost = _weighted_average(
                crude_trades.get(locality_id, []),
                world.last_crude_price_by_locality[locality_id],
            )
            processing_cost = refinery_processing_costs.get(refinery.id, refinery.processing_cost_per_bbl)
            for product in PRODUCTS:
                produced = processed * refinery.yield_shares[product] * efficiency_boost
                unit_cost = (
                    crude_feedstock_cost * PRODUCT_CRUDE_PASS_THROUGH[product]
                    + processing_cost
                    + PRODUCT_CONVERSION_PREMIUM[product]
                )
                _add_product_inventory(world, locality_id, product, produced, unit_cost)
        world.crude_inventory[locality_id] = max(0.0, available_crude - consumed)

    demand_by_locality_product = {
        locality_id: {product: 0.0 for product in PRODUCTS}
        for locality_id in world.localities
    }
    fulfilled_by_locality_product = {
        locality_id: {product: 0.0 for product in PRODUCTS}
        for locality_id in world.localities
    }
    unmet_by_locality_product = {
        locality_id: {product: 0.0 for product in PRODUCTS}
        for locality_id in world.localities
    }
    product_auction = _clear_product_auction(
        world,
        config,
        policy,
        scenario,
        strategy,
        effective_routes,
        demand_by_locality_product,
        fulfilled_by_locality_product,
        unmet_by_locality_product,
    )
    product_trades = product_auction.trades
    _apply_baseline_commercial_balancing(
        scenario,
        demand_by_locality_product,
        fulfilled_by_locality_product,
        unmet_by_locality_product,
        product_auction.agent_product_outcomes,
    )

    for locality_id, inventory in world.product_inventory.items():
        for product, volume in inventory.items():
            carry_limit = world.localities[locality_id].base_product_demand_bbl_week[product] * 1.8
            inventory[product] = min(volume * 0.98, carry_limit)

    new_crude_prices: dict[str, float] = {}
    new_product_prices: dict[str, dict[str, float]] = {}
    locality_shortage_ratio: dict[str, float] = {}
    product_fulfillment_ratio: dict[str, dict[str, float]] = {}

    for locality_id, locality in world.localities.items():
        local_total_demand = sum(demand_by_locality_product[locality_id].values())
        local_total_unmet = sum(unmet_by_locality_product[locality_id].values())
        locality_shortage_ratio[locality_id] = _safe_div(local_total_unmet, local_total_demand)

        accepted_crude_prices = [price for _, price in crude_trades.get(locality_id, [])]
        marginal_accepted = max(accepted_crude_prices) if accepted_crude_prices else 0.0
        marginal_rejected = max(crude_rejected_bids.get(locality_id, []), default=0.0)
        future_cover = _safe_div(world.crude_inventory[locality_id], locality.baseline_refinery_throughput_bbl_week)
        if marginal_accepted > 0.0 and marginal_rejected > 0.0:
            rejected_premium = max(0.0, marginal_rejected - marginal_accepted)
            observed_crude = max(marginal_accepted, min(marginal_rejected, marginal_accepted + rejected_premium * 0.55 + 6.0))
        elif marginal_accepted > 0.0:
            observed_crude = marginal_accepted
        elif marginal_rejected > 0.0:
            last_crude = world.last_crude_price_by_locality[locality_id]
            jump_limit = 1.16 + max(0.0, locality.fear_multiplier - 1.0) * 0.18 + locality_shortage_ratio[locality_id] * 0.20
            observed_crude = max(last_crude * 1.04, min(marginal_rejected, last_crude * jump_limit))
        else:
            observed_crude = world.last_crude_price_by_locality[locality_id]
        last_crude = world.last_crude_price_by_locality[locality_id]
        accepted_jump_limit = 1.30 + max(0.0, locality.fear_multiplier - 1.0) * 0.18 + locality_shortage_ratio[locality_id] * 0.22
        observed_crude = min(observed_crude, last_crude * accepted_jump_limit)
        cover_markup = 1.0 + max(0.0, 0.85 - future_cover) * 0.28
        rejected_reference = marginal_accepted if marginal_accepted > 0.0 else world.last_crude_price_by_locality[locality_id]
        rejected_pressure = max(0.0, marginal_rejected - rejected_reference) / max(rejected_reference, 1.0)
        cover_markup += min(0.24, rejected_pressure * 0.42)
        if marginal_rejected > 0.0 and marginal_accepted == 0.0:
            cover_markup += 0.10
        shortage_markup = 1.0 + locality_shortage_ratio[locality_id] * 0.65 + max(0.0, locality.fear_multiplier - 1.0) * 0.35
        crude_noise = 1.0 + _stable_noise(config.seed, world.week, f"crude-price:{locality_id}") * 0.025
        new_crude_prices[locality_id] = _clamp(observed_crude * cover_markup * shortage_markup * crude_noise, 24.0, 260.0)

        product_fulfillment_ratio[locality_id] = {}
        new_product_prices[locality_id] = {}
        for product in PRODUCTS:
            demand = demand_by_locality_product[locality_id][product]
            fulfilled = fulfilled_by_locality_product[locality_id][product]
            shortage = _safe_div(unmet_by_locality_product[locality_id][product], demand)
            product_fulfillment_ratio[locality_id][product] = _safe_div(fulfilled, demand) if demand > 0 else 1.0
            traded_prices = [price for _, price in product_trades.get((locality_id, product), [])]
            replacement_ask = _product_ask_price(world, locality_id, product, world.product_inventory[locality_id][product])
            if traded_prices:
                observed_price = max(traded_prices)
            else:
                observed_price = replacement_ask * (1.0 + shortage * 0.35)
            stress_markup = 1.0 + shortage * 0.62 + max(0.0, locality.fear_multiplier - 1.0) * 0.30
            product_noise = 1.0 + _stable_noise(config.seed, world.week, f"product-price:{locality_id}:{product}") * 0.030
            new_product_prices[locality_id][product] = _clamp(
                max(observed_price, replacement_ask * 0.92) * stress_markup * product_noise,
                BASE_PRODUCT_PRICES[product] * 0.55,
                BASE_PRODUCT_PRICES[product] * 4.2,
            )

    _post_clear_locality_fear(world, scenario, locality_shortage_ratio)

    world.last_crude_price_by_locality = new_crude_prices
    world.last_product_prices = new_product_prices

    strategic_weight_total = sum(STRATEGIC_LOCALITY_WEIGHTS.values())
    strategic_jet_fulfillment = sum(
        STRATEGIC_LOCALITY_WEIGHTS[locality_id] * product_fulfillment_ratio[locality_id]["jet"]
        for locality_id in world.localities
    ) / strategic_weight_total
    strategic_diesel_fulfillment = sum(
        STRATEGIC_LOCALITY_WEIGHTS[locality_id] * product_fulfillment_ratio[locality_id]["diesel"]
        for locality_id in world.localities
    ) / strategic_weight_total
    military_jet_fulfillment = (
        _safe_div(product_auction.military_fulfilled_by_product["jet"], product_auction.military_demand_by_product["jet"])
        if product_auction.military_demand_by_product["jet"] > 0.0
        else strategic_jet_fulfillment
    )
    military_diesel_fulfillment = (
        _safe_div(product_auction.military_fulfilled_by_product["diesel"], product_auction.military_demand_by_product["diesel"])
        if product_auction.military_demand_by_product["diesel"] > 0.0
        else strategic_diesel_fulfillment
    )
    jet_fuel_fulfillment = military_jet_fulfillment
    diesel_fulfillment = military_diesel_fulfillment
    readiness_components = {
        "jet_fuel_fulfillment": jet_fuel_fulfillment,
        "diesel_fulfillment": diesel_fulfillment,
    }
    readiness_weights = _readiness_product_weights(strategy)
    readiness_index = 100.0 * (
        (jet_fuel_fulfillment * readiness_weights["jet"])
        + (diesel_fulfillment * readiness_weights["diesel"])
    )

    total_shortage = sum(sum(products.values()) for products in unmet_by_locality_product.values())
    total_demand = sum(sum(products.values()) for products in demand_by_locality_product.values())
    average_refinery_utilization = sum(refinery_utilization.values()) / max(1, len(refinery_utilization))
    spr_benchmark_price = _crude_benchmark(new_crude_prices)
    strategic_reserve_market_value_usd = world.strategic_reserve_inventory_bbl * spr_benchmark_price
    strategic_reserve_capacity_ratio = _safe_div(world.strategic_reserve_inventory_bbl, world.strategic_reserve_capacity_bbl)
    strategic_reserve_book_value_usd = world.strategic_reserve_inventory_bbl * SPR_BOOK_COST_PER_BBL
    strategic_reserve_pending_return_bbl = sum(
        scheduled_return.volume_bbl
        for scheduled_return in world.strategic_reserve_pending_returns
    )
    household_fuel_affordability, industrial_output_at_risk, industrial_output = _calculate_economic_indicators(
        new_product_prices,
        product_auction.agent_product_outcomes,
    )
    northcom_household = household_fuel_affordability.get("NORTHCOM", {})
    northcom_industrial = industrial_output_at_risk.get("NORTHCOM", {})
    northcom_output = industrial_output.get("NORTHCOM", {})
    global_industrial_output_weight = sum(
        locality_scores.get("input_weight_bbl", 0.0)
        for locality_scores in industrial_output.values()
    )
    global_industrial_output = (
        sum(
            locality_scores.get("overall", 100.0) * locality_scores.get("input_weight_bbl", 0.0)
            for locality_scores in industrial_output.values()
        )
        / global_industrial_output_weight
        if global_industrial_output_weight > 0.0
        else 100.0
    )

    placeholder_result = StepResult(
        week=world.week,
        crude_price_by_locality=new_crude_prices,
        product_prices=new_product_prices,
        unmet_demand_by_locality_product=unmet_by_locality_product,
        refinery_utilization=refinery_utilization,
        readiness_index=readiness_index,
        readiness_components=readiness_components,
        top_events=[],
        locality_shortage_ratio=locality_shortage_ratio,
        product_fulfillment_ratio=product_fulfillment_ratio,
        locality_crude_inventory_bbl=dict(world.crude_inventory),
        locality_product_inventory_bbl={loc: dict(values) for loc, values in world.product_inventory.items()},
        strategic_reserve_inventory_bbl=world.strategic_reserve_inventory_bbl,
        strategic_reserve_market_value_usd=strategic_reserve_market_value_usd,
        strategic_reserve_capacity_ratio=strategic_reserve_capacity_ratio,
        strategic_reserve_released_bbl=reserve_operation.released_bbl,
        strategic_reserve_purchased_bbl=reserve_operation.purchased_bbl,
        strategic_reserve_returned_bbl=reserve_operation.returned_bbl,
        household_fuel_affordability=household_fuel_affordability,
        industrial_output_at_risk=industrial_output_at_risk,
        industrial_output=industrial_output,
        metrics={
            "total_shortage_bbl": total_shortage,
            "total_demand_bbl": total_demand,
            "global_shortage_ratio": _safe_div(total_shortage, total_demand),
            "average_refinery_utilization": average_refinery_utilization,
            "northcom_household_fuel_affordability": northcom_household.get("overall", 100.0),
            "northcom_household_fuel_price_burden": northcom_household.get("price_burden_ratio", 1.0),
            "northcom_household_fuel_fulfillment": northcom_household.get("fulfillment_ratio", 1.0),
            "northcom_industrial_output_at_risk": northcom_industrial.get("overall", 0.0),
            "northcom_industrial_shortage_component": northcom_industrial.get("shortage_component", 0.0),
            "northcom_industrial_price_component": northcom_industrial.get("price_component", 0.0),
            "northcom_industrial_output": northcom_output.get("overall", 100.0),
            "northcom_industrial_oil_input_ratio": northcom_output.get("oil_input_ratio", 1.0),
            "global_industrial_output": global_industrial_output,
            "jet_fuel_fulfillment": jet_fuel_fulfillment,
            "diesel_fulfillment": diesel_fulfillment,
            "aviation_jet_fulfillment": strategic_jet_fulfillment,
            "heavy_diesel_fulfillment": strategic_diesel_fulfillment,
            "military_jet_demand_bbl": product_auction.military_demand_by_product["jet"],
            "military_diesel_demand_bbl": product_auction.military_demand_by_product["diesel"],
            "military_jet_fulfilled_bbl": product_auction.military_fulfilled_by_product["jet"],
            "military_diesel_fulfilled_bbl": product_auction.military_fulfilled_by_product["diesel"],
            "military_jet_fulfillment": military_jet_fulfillment,
            "military_diesel_fulfillment": military_diesel_fulfillment,
            "strategic_market_jet_fulfillment": strategic_jet_fulfillment,
            "strategic_market_diesel_fulfillment": strategic_diesel_fulfillment,
            "readiness_jet_weight": readiness_weights["jet"],
            "readiness_diesel_weight": readiness_weights["diesel"],
            "spr_inventory_bbl": world.strategic_reserve_inventory_bbl,
            "spr_capacity_ratio": strategic_reserve_capacity_ratio,
            "spr_market_value_usd": strategic_reserve_market_value_usd,
            "spr_book_value_usd": strategic_reserve_book_value_usd,
            "spr_cash_usd": world.strategic_reserve_cash_usd,
            "spr_pending_return_bbl": strategic_reserve_pending_return_bbl,
            "spr_released_bbl": reserve_operation.released_bbl,
            "spr_purchased_bbl": reserve_operation.purchased_bbl,
            "spr_returned_bbl": reserve_operation.returned_bbl,
            "spr_sale_revenue_usd": reserve_operation.sale_revenue_usd,
            "spr_purchase_cost_usd": reserve_operation.purchase_cost_usd,
        },
    )
    placeholder_result.top_events = _generate_events(
        world,
        placeholder_result,
        scenario,
        reserve_operation,
        blocked_routes,
        crude_trades,
        crude_rejected_bids,
        previous_crude_prices,
        previous_shortage_ratio,
    )

    world.metrics = dict(placeholder_result.metrics)
    world.history.append(placeholder_result)
    return placeholder_result


def run_n_steps(
    world: WorldState,
    config: SimulationConfig,
    scenarios: dict[str, ScenarioPreset],
    steps: int,
    military_strategies: dict[str, MilitaryStrategyPreset] | None = None,
) -> list[StepResult]:
    results: list[StepResult] = []
    for _ in range(steps):
        results.append(step_world(world, config, scenarios, military_strategies))
    return results
