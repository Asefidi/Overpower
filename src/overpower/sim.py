from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any

PRODUCTS = ("gasoline", "diesel", "jet")
SECTORS = ("heavy_logistics", "aviation", "agriculture", "light_logistics", "other")
HOUSEHOLD_QUARTILES = ("q1", "q2", "q3", "q4")
STRATEGIC_PRODUCTS = {("heavy_logistics", "diesel"), ("aviation", "jet")}
BASE_PRODUCT_PRICES = {"gasoline": 112.0, "diesel": 126.0, "jet": 138.0}
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


@dataclass(slots=True)
class PolicyControls:
    reserve_release_kbd: float = 0.0
    refinery_subsidy_pct: float = 0.0
    military_priority_pct: float = 0.0
    shipping_cost_multiplier: float = 1.0


@dataclass(slots=True)
class SimulationConfig:
    seed: int = 0
    start_week: int = 0
    selected_scenario: str = "baseline"
    route_overrides: dict[tuple[str, str], dict[str, float | int | bool]] = field(default_factory=dict)
    policy_controls: PolicyControls = field(default_factory=PolicyControls)
    demand_sensitivity: float = 0.20
    inventory_cover_weeks: float = 1.35


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
class ScenarioPreset:
    name: str
    description: str
    route_overrides: dict[tuple[str, str], dict[str, float | int | bool]] = field(default_factory=dict)
    locality_fear_shocks: dict[str, float] = field(default_factory=dict)
    producer_supply_shocks: dict[str, float] = field(default_factory=dict)
    producer_country_shocks: dict[str, float] = field(default_factory=dict)
    refinery_capacity_shocks: dict[str, float] = field(default_factory=dict)
    refinery_country_shocks: dict[str, float] = field(default_factory=dict)
    policy_defaults: PolicyControls = field(default_factory=PolicyControls)


@dataclass(slots=True)
class StepResult:
    week: int
    crude_price_by_locality: dict[str, float]
    product_prices: dict[str, dict[str, float]]
    unmet_demand_by_locality_product: dict[str, dict[str, float]]
    refinery_utilization: dict[str, float]
    readiness_index: float
    top_events: list[str]
    locality_shortage_ratio: dict[str, float]
    product_fulfillment_ratio: dict[str, dict[str, float]]
    locality_crude_inventory_bbl: dict[str, float]
    locality_product_inventory_bbl: dict[str, dict[str, float]]
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


def _weighted_average(trades: list[tuple[float, float]], fallback: float) -> float:
    volume = sum(volume for volume, _ in trades)
    if volume <= 0:
        return fallback
    return sum(volume * price for volume, price in trades) / volume


def _copy_routes(routes: dict[tuple[str, str], RouteState]) -> dict[tuple[str, str], RouteState]:
    return {key: replace(route) for key, route in routes.items()}


def _effective_policy(config: SimulationConfig, scenario: ScenarioPreset) -> PolicyControls:
    return PolicyControls(
        reserve_release_kbd=scenario.policy_defaults.reserve_release_kbd + config.policy_controls.reserve_release_kbd,
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
    return routes


def _allocate_reserve_release(world: WorldState, policy: PolicyControls) -> dict[str, float]:
    if policy.reserve_release_kbd <= 0:
        return {}
    released_bbl = policy.reserve_release_kbd * 1_000.0 * 7.0
    distribution: dict[str, float] = {}
    for locality, weight in RESERVE_RELEASE_WEIGHTS.items():
        if locality not in world.crude_inventory:
            continue
        addition = released_bbl * weight
        world.crude_inventory[locality] += addition
        distribution[locality] = addition
    return distribution


def _resolve_arrivals(world: WorldState) -> None:
    remaining: list[Shipment] = []
    for shipment in world.shipments_in_transit:
        if shipment.arrival_week <= world.week:
            world.crude_inventory[shipment.destination] += shipment.volume_bbl
        else:
            remaining.append(shipment)
    world.shipments_in_transit = remaining


def _global_product_prices(world: WorldState) -> dict[str, float]:
    result: dict[str, float] = {}
    for product in PRODUCTS:
        prices = [world.last_product_prices[locality][product] for locality in world.localities]
        result[product] = sum(prices) / max(1, len(prices))
    return result


def _producer_supply_offer(
    producer: CrudeProducerAgent,
    world: WorldState,
    scenario: ScenarioPreset,
) -> tuple[float, float]:
    locality = world.localities[producer.locality]
    supply_shock = scenario.producer_supply_shocks.get(producer.locality, 1.0)
    supply_shock *= scenario.producer_country_shocks.get(producer.country, 1.0)
    available = producer.baseline_supply_bbl_week * max(0.05, supply_shock)
    scarcity = max(0.0, 1.0 - supply_shock) * 16.0
    fear_markup = (locality.fear_multiplier - 1.0) * (5.5 + producer.risk_weight * 2.0)
    inventory_pressure = max(
        0.0,
        1.0 - _safe_div(world.crude_inventory[producer.locality], locality.baseline_refinery_throughput_bbl_week * 1.4),
    )
    ask = producer.cost_floor_per_bbl + scarcity + fear_markup + inventory_pressure * 4.0
    return available, max(24.0, ask)


def _refinery_target_need(
    refinery: RefineryAgent,
    world: WorldState,
    policy: PolicyControls,
    scenario: ScenarioPreset,
) -> tuple[float, float, float]:
    global_prices = _global_product_prices(world)
    shock = scenario.refinery_capacity_shocks.get(refinery.locality, 1.0)
    shock *= scenario.refinery_country_shocks.get(refinery.country, 1.0)
    subsidy_boost = 1.0 + policy.refinery_subsidy_pct * 0.30
    target_throughput = refinery.weekly_crude_capacity_bbl * refinery.baseline_utilization * shock * subsidy_boost
    target_throughput = min(target_throughput, refinery.weekly_crude_capacity_bbl * (1.0 + policy.refinery_subsidy_pct * 0.15))
    basket_value = sum(refinery.yield_shares[product] * global_prices[product] for product in PRODUCTS)
    processing_cost = refinery.processing_cost_per_bbl * (1.0 - policy.refinery_subsidy_pct)
    willingness_to_pay = max(30.0, basket_value - processing_cost - 7.5)
    return target_throughput, processing_cost, willingness_to_pay


def _product_ask_price(world: WorldState, locality_id: str, product: str, available_bbl: float) -> float:
    locality = world.localities[locality_id]
    base_demand = locality.base_product_demand_bbl_week[product]
    coverage = _safe_div(available_bbl, base_demand)
    scarcity = max(0.0, 0.90 - coverage) * 0.25
    fear_markup = max(0.0, locality.fear_multiplier - 1.0) * 0.12
    return max(BASE_PRODUCT_PRICES[product] * 0.75, world.last_product_prices[locality_id][product] * (1.0 + scarcity + fear_markup))


def _demand_for_agent(
    agent: DemandAgent,
    world: WorldState,
    policy: PolicyControls,
    config: SimulationConfig,
) -> tuple[dict[str, float], dict[str, float]]:
    locality = world.localities[agent.locality]
    demand: dict[str, float] = {}
    bids: dict[str, float] = {}
    for product in PRODUCTS:
        base = agent.base_demand_bbl_week[product]
        backlog_ratio = _safe_div(agent.backlog_bbl[product], max(base, 1.0))
        quantity = base * (1.0 + min(0.45, backlog_ratio * config.demand_sensitivity))
        demand[product] = quantity
        priority = agent.price_priority[product]
        strategic_boost = 0.0
        if (agent.segment, product) in STRATEGIC_PRODUCTS:
            strategic_boost = policy.military_priority_pct
        bids[product] = (
            BASE_PRODUCT_PRICES[product]
            * priority
            * agent.income_multiplier
            * locality.fear_multiplier
            * (1.0 + strategic_boost)
            * (1.0 + min(0.10, backlog_ratio * 0.05))
        )
    return demand, bids


def _generate_events(
    world: WorldState,
    step: StepResult,
    scenario: ScenarioPreset,
    reserve_distribution: dict[str, float],
    blocked_routes: list[tuple[str, str]],
    crude_trades: dict[str, list[tuple[float, float]]],
) -> list[str]:
    events: list[str] = []
    if blocked_routes:
        origin, destination = blocked_routes[0]
        events.append(
            f"Route pressure: {world.localities[origin].label} -> {world.localities[destination].label} is blocked, forcing cargo onto longer lanes."
        )

    most_stressed = sorted(step.locality_shortage_ratio.items(), key=lambda item: item[1], reverse=True)
    if most_stressed and most_stressed[0][1] > 0.05:
        locality_id, shortage = most_stressed[0]
        worst_product = max(
            PRODUCTS,
            key=lambda product: step.unmet_demand_by_locality_product[locality_id][product],
        )
        events.append(
            f"Market clearing: {world.localities[locality_id].label} shows {shortage:.0%} aggregate shortage, led by {worst_product} stress."
        )

    if reserve_distribution:
        biggest_locality = max(reserve_distribution, key=reserve_distribution.get)
        events.append(
            f"Policy response: reserve release adds {reserve_distribution[biggest_locality] / 1_000_000:.2f}M bbl to {world.localities[biggest_locality].label}."
        )

    if crude_trades:
        spiking_locality = max(crude_trades, key=lambda loc: _weighted_average(crude_trades[loc], world.last_crude_price_by_locality[loc]))
        observed_price = _weighted_average(crude_trades[spiking_locality], world.last_crude_price_by_locality[spiking_locality])
        if observed_price > world.last_crude_price_by_locality[spiking_locality] * 1.03:
            events.append(
                f"Crude markets: delivered feedstock into {world.localities[spiking_locality].label} cleared near ${observed_price:.0f}/bbl."
            )

    if scenario.name != "Baseline" and len(events) < 3:
        events.append(f"Scenario pressure remains active: {scenario.description}")

    return events[:3]


def step_world(
    world: WorldState,
    config: SimulationConfig,
    scenarios: dict[str, ScenarioPreset],
) -> StepResult:
    scenario = scenarios[config.selected_scenario]
    policy = _effective_policy(config, scenario)

    world.week += 1
    _resolve_arrivals(world)
    effective_routes = _effective_routes(world, config, scenario, policy)
    blocked_routes = [key for key, route in effective_routes.items() if key[0] != key[1] and route.blocked]
    reserve_distribution = _allocate_reserve_release(world, policy)

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
    procurement_requests: list[tuple[float, str, RefineryAgent, float]] = []

    for refinery in world.refiners:
        target_throughput, processing_cost, willingness_to_pay = _refinery_target_need(refinery, world, policy, scenario)
        locality_inventory = world.crude_inventory[refinery.locality]
        locality_total_capacity = max(1.0, locality_capacity_totals.get(refinery.locality, refinery.weekly_crude_capacity_bbl))
        inventory_share = locality_inventory * refinery.weekly_crude_capacity_bbl / locality_total_capacity
        desired_cover = target_throughput * config.inventory_cover_weeks
        request_volume = max(0.0, desired_cover - inventory_share)
        refinery_targets[refinery.id] = target_throughput
        refinery_mwtp[refinery.id] = willingness_to_pay
        refinery_processing_costs[refinery.id] = processing_cost
        procurement_requests.append((willingness_to_pay, refinery.id, refinery, request_volume))

    procurement_requests.sort(key=lambda item: item[0], reverse=True)

    producer_offers: list[dict[str, Any]] = []
    for producer in world.producers:
        available, ask = _producer_supply_offer(producer, world, scenario)
        producer_offers.append({"producer": producer, "remaining": available, "ask": ask})

    route_remaining_capacity = {
        key: route.base_capacity_bbl * route.capacity_multiplier for key, route in effective_routes.items()
    }
    crude_trades: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for _, refinery_id, refinery, request_volume in procurement_requests:
        if request_volume <= 1.0:
            continue
        candidates: list[tuple[float, dict[str, Any], RouteState]] = []
        for offer in producer_offers:
            if offer["remaining"] <= 1.0:
                continue
            route = effective_routes[(offer["producer"].locality, refinery.locality)]
            if route.blocked:
                continue
            delivered_cost = offer["ask"] + route.shipping_cost_per_bbl
            if delivered_cost > refinery_mwtp[refinery_id]:
                continue
            candidates.append((delivered_cost, offer, route))
        candidates.sort(key=lambda item: item[0])

        remaining_need = request_volume
        for delivered_cost, offer, route in candidates:
            key = (offer["producer"].locality, refinery.locality)
            capacity_left = route_remaining_capacity[key]
            if capacity_left <= 1.0:
                continue
            volume = min(remaining_need, offer["remaining"], capacity_left)
            if volume <= 1.0:
                continue
            route_remaining_capacity[key] -= volume
            offer["remaining"] -= volume
            remaining_need -= volume
            crude_trades[refinery.locality].append((volume, delivered_cost))
            if route.latency_weeks == 0:
                world.crude_inventory[refinery.locality] += volume
            else:
                world.shipments_in_transit.append(
                    Shipment(
                        origin=offer["producer"].locality,
                        destination=refinery.locality,
                        volume_bbl=volume,
                        arrival_week=world.week + route.latency_weeks,
                        unit_cost_per_bbl=delivered_cost,
                        supplier_id=offer["producer"].id,
                        buyer_id=refinery.id,
                    )
                )
            if remaining_need <= 1.0:
                break

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
            for product in PRODUCTS:
                produced = processed * refinery.yield_shares[product] * efficiency_boost
                world.product_inventory[locality_id][product] += produced
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
    product_trades: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for product in PRODUCTS:
        agent_orders: list[tuple[float, DemandAgent, float]] = []
        for agent in world.demand_agents:
            quantities, bids = _demand_for_agent(agent, world, policy, config)
            demand = quantities[product]
            bid = bids[product]
            if demand <= 1.0:
                continue
            agent_orders.append((bid, agent, demand))
            demand_by_locality_product[agent.locality][product] += demand
        agent_orders.sort(key=lambda item: item[0], reverse=True)

        source_asks = {
            locality_id: _product_ask_price(world, locality_id, product, world.product_inventory[locality_id][product])
            for locality_id in world.localities
        }

        for bid, agent, demand in agent_orders:
            remaining = demand
            candidates: list[tuple[float, str]] = []
            for source_locality in world.localities:
                available = world.product_inventory[source_locality][product]
                if available <= 1.0:
                    continue
                route = effective_routes[(source_locality, agent.locality)]
                if route.blocked:
                    continue
                delivered_cost = source_asks[source_locality] + route.shipping_cost_per_bbl * 0.65
                candidates.append((delivered_cost, source_locality))
            candidates.sort(key=lambda item: item[0])

            spend = 0.0
            fulfilled = 0.0
            for delivered_cost, source_locality in candidates:
                if remaining <= 1.0:
                    break
                available = world.product_inventory[source_locality][product]
                volume = min(remaining, available)
                if volume <= 1.0:
                    continue
                world.product_inventory[source_locality][product] -= volume
                remaining -= volume
                fulfilled += volume
                spend += volume * delivered_cost
                fulfilled_by_locality_product[agent.locality][product] += volume
                product_trades[(agent.locality, product)].append((volume, delivered_cost))
            unmet = max(0.0, demand - fulfilled)
            unmet_by_locality_product[agent.locality][product] += unmet
            agent.backlog_bbl[product] = min(agent.base_demand_bbl_week[product] * 1.8, agent.backlog_bbl[product] * 0.35 + unmet * 0.65)

    for locality_id, inventory in world.product_inventory.items():
        for product, volume in inventory.items():
            carry_limit = world.localities[locality_id].base_product_demand_bbl_week[product] * 1.8
            inventory[product] = min(volume * 0.98, carry_limit)

    new_crude_prices: dict[str, float] = {}
    new_product_prices: dict[str, dict[str, float]] = {}
    locality_shortage_ratio: dict[str, float] = {}
    product_fulfillment_ratio: dict[str, dict[str, float]] = {}

    for locality_id, locality in world.localities.items():
        fallback_crude = world.last_crude_price_by_locality[locality_id]
        observed_crude = _weighted_average(crude_trades.get(locality_id, []), fallback_crude)
        future_cover = _safe_div(world.crude_inventory[locality_id], locality.baseline_refinery_throughput_bbl_week)
        cover_markup = max(0.0, 0.8 - future_cover) * 0.08
        new_crude_prices[locality_id] = _clamp(fallback_crude * 0.72 + observed_crude * 0.28 * (1.0 + cover_markup), 32.0, 180.0)

        local_total_demand = sum(demand_by_locality_product[locality_id].values())
        local_total_unmet = sum(unmet_by_locality_product[locality_id].values())
        locality_shortage_ratio[locality_id] = _safe_div(local_total_unmet, local_total_demand)

        product_fulfillment_ratio[locality_id] = {}
        new_product_prices[locality_id] = {}
        for product in PRODUCTS:
            demand = demand_by_locality_product[locality_id][product]
            fulfilled = fulfilled_by_locality_product[locality_id][product]
            shortage = _safe_div(unmet_by_locality_product[locality_id][product], demand)
            product_fulfillment_ratio[locality_id][product] = _safe_div(fulfilled, demand) if demand > 0 else 1.0
            fallback_price = world.last_product_prices[locality_id][product]
            observed_price = _weighted_average(product_trades.get((locality_id, product), []), fallback_price)
            stress_markup = 1.0 + shortage * 0.45 + max(0.0, locality.fear_multiplier - 1.0) * 0.10
            new_product_prices[locality_id][product] = _clamp(
                fallback_price * 0.68 + observed_price * 0.32 * stress_markup,
                BASE_PRODUCT_PRICES[product] * 0.65,
                BASE_PRODUCT_PRICES[product] * 2.6,
            )

    for locality_id, locality in world.localities.items():
        target_fear = 1.0 + scenario.locality_fear_shocks.get(locality_id, 0.0) + locality_shortage_ratio[locality_id] * 0.85
        locality.fear_multiplier = _clamp(locality.fear_multiplier * 0.55 + target_fear * 0.45, 0.85, 2.4)

    world.last_crude_price_by_locality = new_crude_prices
    world.last_product_prices = new_product_prices

    strategic_weight_total = sum(STRATEGIC_LOCALITY_WEIGHTS.values())
    aviation_ratio = sum(
        STRATEGIC_LOCALITY_WEIGHTS[locality_id] * product_fulfillment_ratio[locality_id]["jet"]
        for locality_id in world.localities
    ) / strategic_weight_total
    heavy_ratio = sum(
        STRATEGIC_LOCALITY_WEIGHTS[locality_id] * product_fulfillment_ratio[locality_id]["diesel"]
        for locality_id in world.localities
    ) / strategic_weight_total
    readiness_index = 100.0 * ((aviation_ratio * 0.60) + (heavy_ratio * 0.40))

    total_shortage = sum(sum(products.values()) for products in unmet_by_locality_product.values())
    total_demand = sum(sum(products.values()) for products in demand_by_locality_product.values())
    average_refinery_utilization = sum(refinery_utilization.values()) / max(1, len(refinery_utilization))

    placeholder_result = StepResult(
        week=world.week,
        crude_price_by_locality=new_crude_prices,
        product_prices=new_product_prices,
        unmet_demand_by_locality_product=unmet_by_locality_product,
        refinery_utilization=refinery_utilization,
        readiness_index=readiness_index,
        top_events=[],
        locality_shortage_ratio=locality_shortage_ratio,
        product_fulfillment_ratio=product_fulfillment_ratio,
        locality_crude_inventory_bbl=dict(world.crude_inventory),
        locality_product_inventory_bbl={loc: dict(values) for loc, values in world.product_inventory.items()},
        metrics={
            "total_shortage_bbl": total_shortage,
            "total_demand_bbl": total_demand,
            "global_shortage_ratio": _safe_div(total_shortage, total_demand),
            "average_refinery_utilization": average_refinery_utilization,
            "aviation_jet_fulfillment": aviation_ratio,
            "heavy_diesel_fulfillment": heavy_ratio,
        },
    )
    placeholder_result.top_events = _generate_events(
        world,
        placeholder_result,
        scenario,
        reserve_distribution,
        blocked_routes,
        crude_trades,
    )

    world.metrics = dict(placeholder_result.metrics)
    world.history.append(placeholder_result)
    return placeholder_result


def run_n_steps(
    world: WorldState,
    config: SimulationConfig,
    scenarios: dict[str, ScenarioPreset],
    steps: int,
) -> list[StepResult]:
    results: list[StepResult] = []
    for _ in range(steps):
        results.append(step_world(world, config, scenarios))
    return results
