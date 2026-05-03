from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from overpower.data import (
    PUBLIC_DOD_OPERATIONAL_FUEL_BBL_YEAR,
    build_world,
    get_military_strategy_presets,
    get_scenario_presets,
)
from overpower.sim import (
    DEFAULT_SHIPPING_COST_MULTIPLIER,
    DEFAULT_SPR_INVENTORY_BBL,
    HOUSEHOLD_QUARTILES,
    SCENARIO_NEUTRAL_SHIPPING_COST_MULTIPLIER,
    PRODUCTS,
    PolicyControls,
    SECTORS,
    SPR_STORAGE_CAPACITY_BBL,
    SimulationConfig,
    _is_country_locality_crude_embargoed,
    run_n_steps,
    step_world,
)


class OverpowerSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = get_scenario_presets()
        self.military_strategies = get_military_strategy_presets()

    def _run(self, scenario: str, steps: int = 4, strategy: str = "steady_state", **policy_kwargs):
        config = SimulationConfig(
            selected_scenario=scenario,
            selected_military_strategy=strategy,
            policy_controls=PolicyControls(**policy_kwargs),
        )
        world = build_world(config)
        results = run_n_steps(world, config, self.scenarios, steps, self.military_strategies)
        return world, results[-1]

    def test_baseline_stability(self) -> None:
        _, latest = self._run("baseline")
        self.assertLess(latest.metrics["global_shortage_ratio"], 0.12)
        self.assertGreater(latest.readiness_index, 85.0)
        self.assertGreater(latest.metrics["average_refinery_utilization"], 0.50)
        self.assertIn("jet_fuel_fulfillment", latest.readiness_components)
        self.assertIn("diesel_fulfillment", latest.readiness_components)
        self.assertAlmostEqual(
            latest.readiness_index,
            100.0
            * (
                latest.readiness_components["jet_fuel_fulfillment"] * latest.metrics["readiness_jet_weight"]
                + latest.readiness_components["diesel_fulfillment"] * latest.metrics["readiness_diesel_weight"]
            ),
        )
        self.assertEqual(latest.metrics["jet_fuel_fulfillment"], latest.readiness_components["jet_fuel_fulfillment"])
        self.assertEqual(latest.metrics["diesel_fulfillment"], latest.readiness_components["diesel_fulfillment"])

    def test_northcom_economic_indicators_are_segmented(self) -> None:
        _, latest = self._run("baseline", steps=1)

        household = latest.household_fuel_affordability["NORTHCOM"]
        industrial = latest.industrial_output_at_risk["NORTHCOM"]
        output = latest.industrial_output["NORTHCOM"]

        self.assertAlmostEqual(latest.metrics["northcom_household_fuel_affordability"], household["overall"])
        self.assertAlmostEqual(latest.metrics["northcom_industrial_output_at_risk"], industrial["overall"])
        self.assertAlmostEqual(latest.metrics["northcom_industrial_output"], output["overall"])
        self.assertAlmostEqual(latest.metrics["northcom_industrial_oil_input_ratio"], output["oil_input_ratio"])
        self.assertGreaterEqual(household["overall"], 0.0)
        self.assertLessEqual(household["overall"], 125.0)
        self.assertGreaterEqual(industrial["overall"], 0.0)
        self.assertLessEqual(industrial["overall"], 1.0)
        self.assertGreaterEqual(output["overall"], 0.0)
        self.assertLessEqual(output["overall"], 100.0)
        self.assertGreaterEqual(output["overall"], 85.0)
        self.assertGreaterEqual(output["oil_input_ratio"], 0.0)
        self.assertLessEqual(output["oil_input_ratio"], 1.0)
        for quartile in HOUSEHOLD_QUARTILES:
            self.assertIn(quartile, household)
            self.assertGreaterEqual(household[quartile], 0.0)
            self.assertLessEqual(household[quartile], 125.0)
        for sector in SECTORS:
            self.assertIn(sector, industrial)
            self.assertIn(sector, output)
            self.assertIn(f"{sector}_shortage_component", industrial)
            self.assertIn(f"{sector}_price_component", industrial)
            self.assertIn(f"{sector}_oil_input_ratio", output)
            self.assertGreaterEqual(industrial[sector], 0.0)
            self.assertLessEqual(industrial[sector], 1.0)
            self.assertGreaterEqual(output[sector], 0.0)
            self.assertLessEqual(output[sector], 100.0)
            self.assertGreaterEqual(output[f"{sector}_oil_input_ratio"], 0.0)
            self.assertLessEqual(output[f"{sector}_oil_input_ratio"], 1.0)

    def test_stress_reduces_industrial_output(self) -> None:
        _, baseline = self._run("baseline")
        _, stressed = self._run("hormuz_squeeze")

        self.assertLess(
            stressed.metrics["northcom_industrial_output"],
            baseline.metrics["northcom_industrial_output"],
        )
        self.assertLess(
            stressed.industrial_output["NORTHCOM"]["overall"],
            baseline.industrial_output["NORTHCOM"]["overall"],
        )

    def test_baseline_remains_stable_through_week_52(self) -> None:
        config = SimulationConfig(selected_scenario="baseline")
        world = build_world(config)
        self.assertEqual(world.history, [])
        self.assertEqual(world.week, 0)

        results = run_n_steps(world, config, self.scenarios, 52)
        week_32 = results[31]
        latest = results[-1]
        average_crude = sum(latest.crude_price_by_locality.values()) / len(latest.crude_price_by_locality)

        self.assertLess(week_32.metrics["global_shortage_ratio"], 0.12)
        self.assertLess(latest.metrics["global_shortage_ratio"], 0.12)
        self.assertLess(max(step.metrics["global_shortage_ratio"] for step in results), 0.12)
        self.assertLess(max(locality.fear_multiplier for locality in world.localities.values()), 1.05)
        self.assertGreater(average_crude, 45.0)
        self.assertLess(average_crude, 120.0)
        self.assertFalse(any("Route pressure" in event for event in week_32.top_events))

    def test_hormuz_squeeze_raises_stress(self) -> None:
        baseline_world, baseline = self._run("baseline")
        stressed_world, stressed = self._run("hormuz_squeeze")
        baseline_avg_crude = sum(baseline.crude_price_by_locality.values()) / len(baseline.crude_price_by_locality)
        stressed_avg_crude = sum(stressed.crude_price_by_locality.values()) / len(stressed.crude_price_by_locality)
        self.assertGreater(stressed.metrics["global_shortage_ratio"], baseline.metrics["global_shortage_ratio"])
        self.assertLess(stressed.readiness_index, baseline.readiness_index)
        self.assertGreaterEqual(stressed.readiness_index, 90.0)
        self.assertGreater(stressed.metrics["military_diesel_fulfillment"], stressed.metrics["strategic_market_diesel_fulfillment"])
        self.assertGreaterEqual(stressed_avg_crude, baseline_avg_crude * 1.15)
        self.assertGreaterEqual(stressed.metrics["global_shortage_ratio"] - baseline.metrics["global_shortage_ratio"], 0.04)
        self.assertGreater(stressed_world.localities["CHINA"].fear_multiplier, baseline_world.localities["CHINA"].fear_multiplier + 0.20)
        self.assertTrue(any("Route pressure" in event for event in stressed.top_events))
        self.assertTrue(any("Panic signal" in event for event in stressed.top_events))

    def test_default_shipping_multiplier_is_user_facing_only(self) -> None:
        config = SimulationConfig()
        self.assertEqual(config.policy_controls.shipping_cost_multiplier, DEFAULT_SHIPPING_COST_MULTIPLIER)
        self.assertEqual(DEFAULT_SHIPPING_COST_MULTIPLIER, 1.0)
        for scenario_key, scenario in self.scenarios.items():
            if scenario_key == "coordinated_mitigation":
                continue
            self.assertEqual(scenario.policy_defaults.shipping_cost_multiplier, SCENARIO_NEUTRAL_SHIPPING_COST_MULTIPLIER)
        self.assertEqual(self.scenarios["coordinated_mitigation"].policy_defaults.shipping_cost_multiplier, 0.95)

    def test_scenarios_expose_operational_notes(self) -> None:
        for scenario in self.scenarios.values():
            self.assertGreaterEqual(len(scenario.operational_notes), 3)

    def test_new_scenarios_have_operational_shocks(self) -> None:
        expected = {
            "taiwan_strait_surge",
            "red_sea_diversion",
            "nato_winter_diesel_crunch",
            "gulf_coast_hurricane",
            "south_china_sea_blockade",
        }
        self.assertTrue(expected.issubset(self.scenarios))
        for scenario_key in expected:
            scenario = self.scenarios[scenario_key]
            self.assertGreaterEqual(len(scenario.operational_notes), 3)
            self.assertTrue(scenario.route_overrides)
            self.assertTrue(
                scenario.locality_fear_shocks
                or scenario.producer_supply_shocks
                or scenario.refinery_capacity_shocks
                or scenario.military_demand_shocks
            )

    def test_south_china_sea_blockade_chokes_china_imports(self) -> None:
        scenario = self.scenarios["south_china_sea_blockade"]
        node_ids = set(build_world().localities)
        blocked_origins = {
            origin
            for (origin, destination), override in scenario.route_overrides.items()
            if destination == "CHINA" and bool(override.get("blocked", False))
        }
        self.assertEqual(blocked_origins, node_ids - {"CHINA", "RUSSIA"})
        self.assertFalse(scenario.route_overrides[("RUSSIA", "CHINA")].get("blocked", False))
        self.assertLessEqual(scenario.route_overrides[("RUSSIA", "CHINA")]["capacity_multiplier"], 0.25)

        _, baseline_first_week = self._run("baseline", steps=1)
        _, blockade_first_week = self._run("south_china_sea_blockade", steps=1)

        self.assertGreater(
            blockade_first_week.locality_shortage_ratio["CHINA"],
            baseline_first_week.locality_shortage_ratio["CHINA"] + 0.20,
        )

        _, baseline = self._run("baseline")
        _, blockade = self._run("south_china_sea_blockade")
        self.assertLess(
            blockade.household_fuel_affordability["CHINA"]["overall"],
            baseline.household_fuel_affordability["CHINA"]["overall"] - 20.0,
        )
        self.assertLess(
            blockade.industrial_output["CHINA"]["overall"],
            baseline.industrial_output["CHINA"]["overall"] - 10.0,
        )
        self.assertGreater(
            blockade.industrial_output_at_risk["CHINA"]["overall"],
            baseline.industrial_output_at_risk["CHINA"]["overall"] + 0.10,
        )

    def test_military_strategy_catalog(self) -> None:
        expected = {
            "steady_state",
            "ground_combat_operations",
            "air_maritime_campaign",
            "distributed_island_defense",
            "rapid_deployment_surge",
            "humanitarian_stability_operations",
        }
        self.assertEqual(set(self.military_strategies), expected)
        for strategy in self.military_strategies.values():
            self.assertGreaterEqual(len(strategy.operational_notes), 3)
            self.assertAlmostEqual(
                strategy.readiness_product_weights["jet"] + strategy.readiness_product_weights["diesel"],
                1.0,
            )

    def test_steady_state_strategy_is_backward_compatible(self) -> None:
        config = SimulationConfig(selected_scenario="baseline")
        legacy_world = build_world(config)
        strategy_world = build_world(config)

        legacy = run_n_steps(legacy_world, config, self.scenarios, 1)[-1]
        explicit = run_n_steps(strategy_world, config, self.scenarios, 1, self.military_strategies)[-1]

        self.assertAlmostEqual(legacy.metrics["military_jet_demand_bbl"], explicit.metrics["military_jet_demand_bbl"])
        self.assertAlmostEqual(legacy.metrics["military_diesel_demand_bbl"], explicit.metrics["military_diesel_demand_bbl"])
        self.assertAlmostEqual(legacy.readiness_index, explicit.readiness_index)

    def test_strategy_specific_fuel_effects(self) -> None:
        _, steady = self._run("baseline", steps=1)
        _, ground = self._run("baseline", steps=1, strategy="ground_combat_operations")
        _, air = self._run("baseline", steps=1, strategy="air_maritime_campaign")

        self.assertGreater(ground.metrics["military_diesel_demand_bbl"], steady.metrics["military_diesel_demand_bbl"] * 1.25)
        self.assertGreater(air.metrics["military_jet_demand_bbl"], steady.metrics["military_jet_demand_bbl"] * 1.30)
        self.assertGreater(ground.metrics["readiness_diesel_weight"], steady.metrics["readiness_diesel_weight"])
        self.assertGreater(air.metrics["readiness_jet_weight"], steady.metrics["readiness_jet_weight"])

    def test_combined_scenario_and_strategy_raise_forward_jet_demand(self) -> None:
        _, steady = self._run("taiwan_strait_surge", steps=1)
        _, campaign = self._run("taiwan_strait_surge", steps=1, strategy="air_maritime_campaign")

        self.assertGreater(campaign.metrics["military_jet_demand_bbl"], steady.metrics["military_jet_demand_bbl"] * 1.30)
        self.assertGreaterEqual(campaign.metrics["readiness_jet_weight"], 0.75)

    def test_policy_overlay_improves_response(self) -> None:
        _, stressed = self._run("hormuz_squeeze")
        _, mitigated = self._run(
            "hormuz_squeeze",
            reserve_release_kbd=700.0,
            refinery_subsidy_pct=0.10,
            military_priority_pct=0.10,
        )
        self.assertLess(mitigated.metrics["global_shortage_ratio"], stressed.metrics["global_shortage_ratio"])
        self.assertGreaterEqual(mitigated.readiness_index, 90.0)
        self.assertGreater(mitigated.metrics["military_jet_fulfillment"], stressed.metrics["military_jet_fulfillment"])
        self.assertGreater(mitigated.metrics["military_diesel_fulfillment"], stressed.metrics["military_diesel_fulfillment"])

    def test_spr_ledger_is_initialized(self) -> None:
        world = build_world()
        self.assertEqual(world.strategic_reserve_inventory_bbl, DEFAULT_SPR_INVENTORY_BBL)
        self.assertEqual(world.strategic_reserve_capacity_bbl, SPR_STORAGE_CAPACITY_BBL)
        self.assertEqual(world.strategic_reserve_pending_returns, [])

    def test_spr_exchange_draws_down_and_schedules_premium_return(self) -> None:
        config = SimulationConfig(
            policy_controls=PolicyControls(
                reserve_release_kbd=100.0,
                reserve_release_mode="exchange",
                reserve_exchange_return_weeks=2,
                reserve_exchange_premium_pct=0.10,
            )
        )
        world = build_world(config)
        initial_inventory = world.strategic_reserve_inventory_bbl

        result = step_world(world, config, self.scenarios)

        expected_release = 100_000.0 * 7.0
        self.assertAlmostEqual(result.strategic_reserve_released_bbl, expected_release)
        self.assertAlmostEqual(world.strategic_reserve_inventory_bbl, initial_inventory - expected_release)
        self.assertAlmostEqual(sum(item.volume_bbl for item in world.strategic_reserve_pending_returns), expected_release * 1.10)
        self.assertEqual(world.strategic_reserve_cash_usd, 0.0)

    def test_spr_sale_adds_cash_without_return_obligation(self) -> None:
        config = SimulationConfig(
            policy_controls=PolicyControls(
                reserve_release_kbd=100.0,
                reserve_release_mode="sale",
            )
        )
        world = build_world(config)

        result = step_world(world, config, self.scenarios)

        self.assertGreater(result.strategic_reserve_released_bbl, 0.0)
        self.assertGreater(world.strategic_reserve_cash_usd, 0.0)
        self.assertEqual(world.strategic_reserve_pending_returns, [])

    def test_spr_purchase_refills_when_benchmark_is_below_ceiling(self) -> None:
        config = SimulationConfig(
            policy_controls=PolicyControls(
                reserve_purchase_kbd=50.0,
                reserve_purchase_price_ceiling_per_bbl=120.0,
            )
        )
        world = build_world(config)
        initial_inventory = world.strategic_reserve_inventory_bbl

        result = step_world(world, config, self.scenarios)

        self.assertGreater(result.strategic_reserve_purchased_bbl, 0.0)
        self.assertAlmostEqual(world.strategic_reserve_inventory_bbl, initial_inventory + result.strategic_reserve_purchased_bbl)
        self.assertLess(world.strategic_reserve_cash_usd, 0.0)

    def test_world_scaffold_matches_scope(self) -> None:
        world = build_world()
        self.assertEqual(len(world.producers), 50)
        self.assertEqual(len(world.refiners), 50)
        self.assertEqual(len(world.demand_agents), 87)
        self.assertEqual(len(world.localities), 9)
        self.assertIn("IRAN", world.localities)
        self.assertIn("CENTCOM", world.localities)
        self.assertNotIn("USCENTCOM-IRAN", world.localities)

    def test_has_dedicated_military_buyers(self) -> None:
        world = build_world()
        military_buyers = [agent for agent in world.demand_agents if agent.agent_kind == "military"]
        self.assertEqual(len(military_buyers), 6)
        buyers_by_locality = {buyer.locality: buyer for buyer in military_buyers}
        self.assertEqual(set(buyers_by_locality), {"NORTHCOM", "EUCOM", "CENTCOM", "INDOPACOM", "AFRICOM", "SOUTHCOM"})
        for locality_id in buyers_by_locality:
            self.assertEqual(buyers_by_locality[locality_id].id, f"{locality_id.lower()}-military-buyer")

        civilian_diesel_priority = max(
            agent.price_priority["diesel"]
            for agent in world.demand_agents
            if agent.agent_kind != "military"
        )
        civilian_jet_priority = max(
            agent.price_priority["jet"]
            for agent in world.demand_agents
            if agent.agent_kind != "military"
        )
        for buyer in military_buyers:
            self.assertGreater(buyer.base_demand_bbl_week["diesel"], 0.0)
            self.assertGreater(buyer.base_demand_bbl_week["jet"], 0.0)
            self.assertEqual(buyer.base_demand_bbl_week["gasoline"], 0.0)
            self.assertGreater(buyer.price_priority["diesel"], civilian_diesel_priority * 3.0)
            self.assertGreater(buyer.price_priority["jet"], civilian_jet_priority * 3.0)

        total_military_demand = sum(
            sum(buyer.base_demand_bbl_week[product] for product in PRODUCTS)
            for buyer in military_buyers
        )
        self.assertAlmostEqual(total_military_demand, PUBLIC_DOD_OPERATIONAL_FUEL_BBL_YEAR / 52.0)
        for locality_id in buyers_by_locality:
            for product in PRODUCTS:
                modeled_demand = sum(
                    agent.base_demand_bbl_week[product]
                    for agent in world.demand_agents
                    if agent.locality == locality_id
                )
                self.assertAlmostEqual(
                    modeled_demand,
                    world.localities[locality_id].base_product_demand_bbl_week[product],
                )

    def test_conflict_spikes_military_fuel_demand(self) -> None:
        _, baseline = self._run("baseline", steps=1)
        _, stressed = self._run("hormuz_squeeze", steps=1)

        self.assertGreater(
            stressed.metrics["military_jet_demand_bbl"],
            baseline.metrics["military_jet_demand_bbl"] * 1.15,
        )
        self.assertGreater(
            stressed.metrics["military_diesel_demand_bbl"],
            baseline.metrics["military_diesel_demand_bbl"] * 1.10,
        )
        self.assertGreater(
            stressed.metrics["military_jet_fulfillment"],
            stressed.metrics["strategic_market_jet_fulfillment"],
        )

    def test_embargoed_locality_routes_have_no_edge_in_baseline(self) -> None:
        world = build_world()
        for embargoed_origin in ("IRAN", "RUSSIA"):
            for embargoed_destination in ("EUCOM", "NORTHCOM"):
                for key in ((embargoed_origin, embargoed_destination), (embargoed_destination, embargoed_origin)):
                    with self.subTest(route=key):
                        route = world.routes[key]
                        self.assertTrue(route.blocked)
                        self.assertEqual(route.capacity_multiplier, 0.0)
                        self.assertEqual(route.base_capacity_bbl, 0.0)
        self.assertFalse(world.routes[("CENTCOM", "EUCOM")].blocked)

    def test_venezuela_crude_is_embargoed_from_northcom_and_eucom(self) -> None:
        world = build_world()
        venezuelan_producer = next(producer for producer in world.producers if producer.country == "Venezuela")
        venezuelan_refinery = next(refinery for refinery in world.refiners if refinery.country == "Venezuela")
        northcom_refinery = next(refinery for refinery in world.refiners if refinery.locality == "NORTHCOM")
        eucom_refinery = next(refinery for refinery in world.refiners if refinery.locality == "EUCOM")
        northcom_producer = next(producer for producer in world.producers if producer.locality == "NORTHCOM")
        eucom_producer = next(producer for producer in world.producers if producer.locality == "EUCOM")

        self.assertTrue(_is_country_locality_crude_embargoed(venezuelan_producer, northcom_refinery))
        self.assertTrue(_is_country_locality_crude_embargoed(venezuelan_producer, eucom_refinery))
        self.assertTrue(_is_country_locality_crude_embargoed(northcom_producer, venezuelan_refinery))
        self.assertTrue(_is_country_locality_crude_embargoed(eucom_producer, venezuelan_refinery))

    def test_hormuz_disrupts_both_iran_and_centcom(self) -> None:
        scenario = self.scenarios["hormuz_squeeze"]
        self.assertLess(scenario.producer_supply_shocks["IRAN"], 1.0)
        self.assertLess(scenario.producer_supply_shocks["CENTCOM"], 1.0)
        self.assertLess(scenario.refinery_capacity_shocks["IRAN"], 1.0)
        self.assertLess(scenario.refinery_capacity_shocks["CENTCOM"], 1.0)
        for origin in ("IRAN", "CENTCOM"):
            for destination in ("EUCOM", "NORTHCOM", "INDOPACOM", "CHINA"):
                override = scenario.route_overrides[(origin, destination)]
                self.assertTrue(override["blocked"])
                self.assertEqual(override["capacity_multiplier"], 0.15)

    def test_household_demand_scales_by_income_and_quartile(self) -> None:
        world = build_world()
        northcom_households = sorted(
            [agent for agent in world.demand_agents if agent.locality == "NORTHCOM" and agent.agent_kind == "household"],
            key=lambda agent: agent.segment,
        )
        africom_households = sorted(
            [agent for agent in world.demand_agents if agent.locality == "AFRICOM" and agent.agent_kind == "household"],
            key=lambda agent: agent.segment,
        )
        self.assertGreater(
            northcom_households[-1].base_demand_bbl_week["gasoline"],
            northcom_households[0].base_demand_bbl_week["gasoline"],
        )
        northcom_household_share = sum(agent.base_demand_bbl_week["gasoline"] for agent in northcom_households) / world.localities["NORTHCOM"].base_product_demand_bbl_week["gasoline"]
        africom_household_share = sum(agent.base_demand_bbl_week["gasoline"] for agent in africom_households) / world.localities["AFRICOM"].base_product_demand_bbl_week["gasoline"]
        self.assertGreater(northcom_household_share, africom_household_share)

    def test_iran_baseline_is_not_perma_short(self) -> None:
        _, baseline = self._run("baseline")
        self.assertLess(baseline.locality_shortage_ratio["IRAN"], 0.15)
        self.assertGreaterEqual(baseline.product_fulfillment_ratio["IRAN"]["gasoline"], 0.85)

    def test_product_logistics_create_in_transit_shipments_and_cost_basis(self) -> None:
        config = SimulationConfig(selected_scenario="baseline")
        world = build_world(config)
        initial_cost_basis = world.product_cost_basis["NORTHCOM"]["diesel"]

        result = step_world(world, config, self.scenarios)

        self.assertTrue(any(shipment.commodity in PRODUCTS for shipment in world.shipments_in_transit))
        self.assertNotEqual(world.product_cost_basis["NORTHCOM"]["diesel"], initial_cost_basis)
        self.assertIn("diesel", result.product_prices["NORTHCOM"])

    def test_app_import_smoke(self) -> None:
        import app  # noqa: F401


if __name__ == "__main__":
    unittest.main()
