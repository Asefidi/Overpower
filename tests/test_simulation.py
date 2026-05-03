from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from overpower.data import build_world, get_scenario_presets
from overpower.sim import PolicyControls, SimulationConfig, run_n_steps


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
        self.assertLess(latest.metrics["global_shortage_ratio"], 0.18)
        self.assertGreater(latest.readiness_index, 78.0)
        self.assertGreater(latest.metrics["average_refinery_utilization"], 0.50)

    def test_hormuz_squeeze_raises_stress(self) -> None:
        _, baseline = self._run("baseline")
        _, stressed = self._run("hormuz_squeeze")
        self.assertGreater(stressed.metrics["global_shortage_ratio"], baseline.metrics["global_shortage_ratio"])
        self.assertLess(stressed.readiness_index, baseline.readiness_index)
        self.assertGreater(stressed.crude_price_by_locality["EUCOM"], baseline.crude_price_by_locality["EUCOM"])
        self.assertGreater(stressed.crude_price_by_locality["CHINA"], baseline.crude_price_by_locality["CHINA"])

    def test_policy_overlay_improves_response(self) -> None:
        _, stressed = self._run("hormuz_squeeze")
        _, mitigated = self._run(
            "hormuz_squeeze",
            reserve_release_kbd=700.0,
            refinery_subsidy_pct=0.10,
            military_priority_pct=0.10,
        )
        self.assertLess(mitigated.metrics["global_shortage_ratio"], stressed.metrics["global_shortage_ratio"])
        self.assertGreaterEqual(mitigated.readiness_index, stressed.readiness_index)

    def test_world_scaffold_matches_scope(self) -> None:
        world = build_world()
        self.assertEqual(len(world.producers), 50)
        self.assertEqual(len(world.refiners), 50)
        self.assertEqual(len(world.demand_agents), 81)
        self.assertEqual(len(world.localities), 9)
        self.assertIn("IRAN", world.localities)
        self.assertIn("CENTCOM", world.localities)
        self.assertNotIn("USCENTCOM-IRAN", world.localities)

    def test_iran_exports_are_sanction_blocked_in_baseline(self) -> None:
        world = build_world()
        self.assertTrue(world.routes[("IRAN", "EUCOM")].blocked)
        self.assertTrue(world.routes[("IRAN", "NORTHCOM")].blocked)
        self.assertFalse(world.routes[("CENTCOM", "EUCOM")].blocked)

    def test_app_import_smoke(self) -> None:
        import app  # noqa: F401


if __name__ == "__main__":
    unittest.main()
