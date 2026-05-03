from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from overpower.data import PUBLIC_DOD_OPERATIONAL_FUEL_BBL_YEAR, build_world, get_scenario_presets
from overpower.sim import (
    DEFAULT_SHIPPING_COST_MULTIPLIER,
    DEFAULT_SPR_INVENTORY_BBL,
    PRODUCTS,
    PolicyControls,
    SPR_STORAGE_CAPACITY_BBL,
    SimulationConfig,
    _is_country_locality_crude_embargoed,
    run_n_steps,
    step_world,
)


class OverpowerSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenarios = get_scenario_presets()

    def _run(self, scenario: str, steps: int = 4, **policy_kwargs):
        config = SimulationConfig(
            selected_scenario=scenario,
            policy_controls=PolicyControls(**policy_kwargs),
        )
        world = build_world(config)
        results = run_n_steps(world, config, self.scenarios, steps)
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
                latest.readiness_components["jet_fuel_fulfillment"] * 0.60
                + latest.readiness_components["diesel_fulfillment"] * 0.40
            ),
        )
        self.assertEqual(latest.metrics["jet_fuel_fulfillment"], latest.readiness_components["jet_fuel_fulfillment"])
        self.assertEqual(latest.metrics["diesel_fulfillment"], latest.readiness_components["diesel_fulfillment"])

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
        self.assertGreaterEqual(stressed.readiness_index, baseline.readiness_index - 3.0)
        self.assertGreaterEqual(stressed.readiness_index, 90.0)
        self.assertGreater(stressed.metrics["military_diesel_fulfillment"], stressed.metrics["strategic_market_diesel_fulfillment"])
        self.assertGreaterEqual(stressed_avg_crude, baseline_avg_crude * 1.15)
        self.assertGreaterEqual(stressed.metrics["global_shortage_ratio"] - baseline.metrics["global_shortage_ratio"], 0.05)
        self.assertGreater(stressed_world.localities["CHINA"].fear_multiplier, baseline_world.localities["CHINA"].fear_multiplier + 0.20)
        self.assertTrue(any("Route pressure" in event for event in stressed.top_events))
        self.assertTrue(any("Panic signal" in event for event in stressed.top_events))

    def test_default_shipping_multiplier_is_user_facing_only(self) -> None:
        config = SimulationConfig()
        self.assertEqual(config.policy_controls.shipping_cost_multiplier, DEFAULT_SHIPPING_COST_MULTIPLIER)
        self.assertEqual(DEFAULT_SHIPPING_COST_MULTIPLIER, 1.5)
        self.assertEqual(self.scenarios["baseline"].policy_defaults.shipping_cost_multiplier, 1.0)
        self.assertEqual(self.scenarios["hormuz_squeeze"].policy_defaults.shipping_cost_multiplier, 1.0)
        self.assertEqual(self.scenarios["cis_disruption"].policy_defaults.shipping_cost_multiplier, 1.0)
        self.assertEqual(self.scenarios["venezuela_outage"].policy_defaults.shipping_cost_multiplier, 1.0)
        self.assertEqual(self.scenarios["coordinated_mitigation"].policy_defaults.shipping_cost_multiplier, 0.95)

    def test_scenarios_expose_operational_notes(self) -> None:
        for scenario in self.scenarios.values():
            self.assertGreaterEqual(len(scenario.operational_notes), 3)

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
        self.assertGreater(mitigated.metrics["strategic_market_jet_fulfillment"], stressed.metrics["strategic_market_jet_fulfillment"])
        self.assertGreater(mitigated.metrics["strategic_market_diesel_fulfillment"], stressed.metrics["strategic_market_diesel_fulfillment"])

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
        self.assertEqual(len(world.demand_agents), 83)
        self.assertEqual(len(world.localities), 9)
        self.assertIn("IRAN", world.localities)
        self.assertIn("CENTCOM", world.localities)
        self.assertNotIn("USCENTCOM-IRAN", world.localities)

    def test_has_dedicated_military_buyers(self) -> None:
        world = build_world()
        military_buyers = [agent for agent in world.demand_agents if agent.agent_kind == "military"]
        self.assertEqual(len(military_buyers), 2)
        buyers_by_locality = {buyer.locality: buyer for buyer in military_buyers}
        self.assertEqual(set(buyers_by_locality), {"NORTHCOM", "INDOPACOM"})
        self.assertEqual(buyers_by_locality["NORTHCOM"].id, "northcom-military-buyer")
        self.assertEqual(buyers_by_locality["INDOPACOM"].id, "indopacom-military-buyer")

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
        for locality_id in ("NORTHCOM", "INDOPACOM"):
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
