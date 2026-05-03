# Overpower

Overpower is an agent-based simulation and Streamlit command-view dashboard for stress-testing the oil and refined-fuel supply chain under geopolitical, logistics, and military-readiness pressure.

The project starts from a simple belief: energy security is not only a question of aggregate supply and demand. It is a system of producers, refiners, shippers, households, industrial users, military buyers, inventories, routes, shocks, expectations, and policy choices interacting under pressure. When that system breaks, it rarely breaks in a smooth, average, linear way.

Overpower is built to make those second-order effects visible. It asks questions like: Which lanes become strategically fragile first? Which regions absorb the shock, and which export it? How do military jet and diesel needs compete with civilian demand during a crisis? When does a reserve release actually buy readiness, and when does it only move scarcity around?

## Why Agent-Based Modeling?

Traditional macro and energy models often compress complex behavior into representative averages. That can be useful, but it can also hide the thing commanders, planners, and policymakers most need to see: how local decisions cascade into system-level stress.

Agent-based models take the opposite route. They model many smaller actors with their own constraints, priorities, inventories, prices, and willingness to pay, then let aggregate outcomes emerge from their interaction. In Overpower, crude producers offer barrels, refineries bid for feedstock, demand agents compete for gasoline/diesel/jet fuel, military buyers bid with higher urgency, route delays push shipments into future weeks, and fear or scarcity feeds back into price formation.

The goal is not false precision. The goal is a better sandbox for strategic reasoning: a place to test assumptions, find nonlinear failure points, compare policy responses, and see how a disruption propagates before it becomes obvious in headline metrics.

## What This Project Seeks To Accomplish

Overpower is a wargaming lab for fuel logistics and economic strategy. It is meant to help users:

- Explore how fossil-fuel shocks propagate from extraction through refining, shipping, and final demand
- Compare geopolitical scenarios with different operational postures
- Test policy levers such as Strategic Petroleum Reserve releases, refinery subsidies, military-priority purchasing, and route overrides
- Track the tradeoff between civilian economic exposure and military readiness
- Surface explainable events, not just final charts, so users can understand why a scenario changed
- Build a foundation for richer future ABMs with more geography, finance, firm strategy, and behavioral dynamics

The current repository is a runnable MVP: a command-aligned model of crude supply, refining, product allocation, shipping routes, Strategic Petroleum Reserve policy, and military fuel buyers competing for diesel and jet fuel. It is designed for scenario comparison and decision support, not official forecasting.

## Current Scope

The simulation models:

- 9 command-aligned localities: `NORTHCOM`, `EUCOM`, `RUSSIA`, `CENTCOM`, `IRAN`, `CHINA`, `INDOPACOM`, `AFRICOM`, and `SOUTHCOM`
- 50 crude producer agents loaded from cleaned country/owner rollups
- 50 refinery agents loaded from cleaned refinery rollups
- 45 sector demand agents across heavy logistics, aviation, agriculture, light logistics, and other oil-intensive activity
- 36 household demand agents, split into four income quartiles per locality
- 6 dedicated military fuel buyers in `NORTHCOM`, `EUCOM`, `CENTCOM`, `INDOPACOM`, `AFRICOM`, and `SOUTHCOM`
- Gasoline, diesel, and jet fuel markets
- Weekly crude and product clearing, route latency, in-transit shipments, inventories, fear multipliers, and price feedback
- Strategic Petroleum Reserve releases, purchases, exchange returns, refinery subsidies, and military-priority purchasing overlays

## Quick Start

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Launch the dashboard:

```bash
streamlit run app.py
```

Run the regression suite:

```bash
python3 -m unittest discover -s tests -v
```

## Dashboard Workflow

The Streamlit app opens to `Overpower Command View`. Use the sidebar to choose a scenario, layer on a military strategy, adjust SPR and refinery-policy controls, and optionally override route status, latency, shipping cost, or capacity.

A typical demo path:

1. Start with `Baseline` and `Steady State`.
2. Click `Run 4 Weeks` and note military jet fulfillment, military diesel fulfillment, global shortage, and average crude price.
3. Switch to `Taiwan Strait Surge` with `Air-Maritime Campaign`, reset, and run 4 weeks.
4. Compare route pressure, readiness components, product prices, shortage heatmaps, refinery utilization, and the event log.
5. Add reserve release, refinery subsidy, or military priority controls and run again to compare mitigation effects.

## Scenarios

Scenario presets represent external shocks to the fuel system. Current presets are:

- `Baseline`
- `Hormuz Squeeze`
- `Russia Disruption`
- `Venezuela Outage`
- `Taiwan Strait Surge`
- `Red Sea Diversion`
- `NATO Winter Diesel Crunch`
- `Gulf Coast Hurricane`
- `South China Sea Blockade`
- `Coordinated Mitigation`

Scenarios can change route capacity, latency, shipping costs, supply, refining capacity, locality fear, military demand pressure, and default policy settings.

## Military Strategies

Military strategies are separate overlays that can be combined with any scenario. They change military fuel demand, bid urgency, and the readiness weighting between jet and diesel fulfillment.

Current presets are:

- `Steady State`
- `Ground Combat Operations`
- `Air-Maritime Campaign`
- `Distributed Island Defense`
- `Rapid Deployment Surge`
- `Humanitarian Stability Operations`

## Outputs

The dashboard highlights:

- Headline date, readiness, shortage, and crude-price KPIs
- Maritime operating picture with pressured and blocked lanes
- Top explainable market events
- Scenario and strategy notes
- SPR inventory, capacity, exchange returns, releases, and purchases
- NORTHCOM and China economic exposure panels
- Crude, gasoline, diesel, jet, shortage, and readiness trends
- Refinery capacity-at-risk rankings
- Locality/product shortage heatmap

The core simulation API is exposed through `src/overpower/`:

- `build_world()`
- `step_world()`
- `run_n_steps()`
- `get_scenario_presets()`
- `get_military_strategy_presets()`

## Project Structure

```text
app.py                         Streamlit entrypoint
src/overpower/sim.py           Simulation dataclasses, clearing logic, policy logic, metrics
src/overpower/data.py          Data loading, locality construction, agents, routes, presets
src/overpower/ui.py            Streamlit dashboard
src/cleaned-data/              Cleaned 50-agent crude and refinery rollups
src/raw-input-data/            Source CSV/XLSX data used by the model
src/scripts/                   Data cleaning and rollup scripts
tests/test_simulation.py       Regression and behavior tests
docs/overpower-design.md       Design notes and modeling intent
```

## Data and Modeling Notes

The model uses public and cleaned project data, including command-region core data, oil production and consumption tables, refinery throughput/capacity data, Global Energy Monitor extraction data, and cleaned refinery inventory data. The model scales crude and refinery agents to locality-level baseline totals, then runs a weekly market-clearing loop.

Important assumptions:

- Crude is treated as a single fungible input.
- Refinery complexity and product yields are approximated from available public/refinery data.
- Product demand is limited to gasoline, diesel, and jet fuel.
- Households are represented by locality-level quartile agents.
- Sector demand is represented by five oil-intensive demand segments per locality.
- Military fuel demand uses a public DoD operational-fuel basis and competes directly for diesel and jet fuel.
- Governments and capital allocators are represented through policy controls, not autonomous agents.
- Scenarios model supply-chain shocks and policy defaults; military strategies model operational posture, not tactical combat outcomes.

## Limitations

Overpower is a hackathon-scale MVP and should be treated as a wargaming and reasoning environment rather than a calibrated forecast system.

It does not currently model currency effects, full macroeconomic feedback, tactical attrition, targeting, weapons effects, refinery-specific crude slates, contractual supply arrangements, financial speculation, or investment decisions by autonomous capital allocators. Route geography is command-node level, not port, pipeline, or facility level.

## Development

The tests cover baseline stability, scenario stress behavior, military strategy overlays, SPR policy mechanics, embargo behavior, demand-agent construction, product logistics, and app import smoke tests.

Run them before making behavioral changes:

```bash
python3 -m unittest discover -s tests -v
```
