# Overpower MVP Spec

## Purpose
Overpower is a scenario-driven agent-based fossil fuel supply chain simulator. The MVP is not trying to be a perfect macro forecast. Its job is to make cascading failure legible: show how a chokepoint shock or policy intervention propagates through production, transit, refining, civilian demand, and military fuel availability.

## Source Hierarchy
1. `README.md` is the source of truth for mission, problem framing, and the long-term research direction.
2. Checked-in local data under `src/cleaned-data/` defines what baseline inputs we actually possess.
3. `codex-README.md` is useful as an MVP scoping draft, but not authoritative where it conflicts with the README or the data.
4. `engine.py` is a prototype scaffold, not a final spec.

## Reconciled Scope
| Topic | `README.md` | `codex-README.md` | MVP Decision |
| --- | --- | --- | --- |
| Mission | Firm-level ABM of the fossil fuel supply chain for strategic forecasting | 5-node non-linear shock simulator for a demo | Build the 5-node simulator now, but preserve a clean path to a richer ABM later |
| Agent granularity | Capital allocators, households, governments, firms | Aggregated producer, refiner, and consumer roles per node | Use aggregated roles inside each node for the MVP; defer governments and capital allocators |
| Time scale | Monthly turns for investment decisions | Daily `step()` loop | Use a daily operational loop in the MVP; defer monthly investment/capex decisions |
| Data | Approximate, constrained by limited access to high-quality data | Fully hardcoded initialized state | Seed from checked-in static data or hardcoded constants only; no live APIs |
| Capacity dynamics | Firms can invest and negotiate | Fixed network with interventions | Keep production and refining capacity fixed for the MVP, except for policy toggles |
| Products | Fuel supply broadly | Gasoline and jet fuel | Track crude plus at least one civilian fuel and one military-relevant fuel; see open question on diesel |

## Product Goals
1. Demonstrate that localized supply shocks can create delayed, non-linear downstream failures.
2. Show how a commander or policymaker can manipulate a few interventions and materially change outcomes.
3. Make civilian pain and military buffering visible at the same time.
4. Be simple, deterministic, and robust enough for a live 3-minute demo.

## Non-Goals For The MVP
1. Full firm-level or country-level realism.
2. Live market data, API integrations, or real-time forecasting.
3. Monthly capital allocation, financing, or speculative behavior.
4. Detailed tax, tariff, and institutional models.
5. Calibrated geopolitical forecasting suitable for operational use.

## MVP Model Boundary
### Regions
The world is abstracted into five macro nodes:
1. `USNORTHCOM`
2. `USCENTCOM`
3. `USEUCOM`
4. `RUSSIA`
5. `INDOPACOM`

These are UI-facing labels. The backing data may come from the closest available rows in `src/cleaned-data/core-data.csv`.

### Agents
Each node contains three aggregated economic roles:
1. Producer: crude extraction and crude inventory management
2. Refiner: crude purchasing, refining, and product inventory management
3. Consumers:
   - 10 household deciles with increasing willingness to pay
   - 1 industrial or strategic demand bucket with high, inelastic demand

Governments and capital allocators are deferred to a later version.

### Commodities
The MVP must represent:
1. Crude oil
2. At least one civilian refined fuel
3. At least one military-relevant refined fuel

The initial default is crude plus gasoline and jet fuel, but diesel is an open design choice because it maps better to trucking, logistics, and agriculture.

### Time
1. One engine step equals one day.
2. Interventions can be persistent toggles or one-shot actions.
3. History is recorded daily for charts and after-action comparison.

## Functional Requirements
1. Initialize the full network from static in-repo data or a checked-in baseline dictionary.
2. Advance the simulation one day at a time with a deterministic `step()` function.
3. Generate crude production into producer inventories each day.
4. Move crude across edges with transit delay and congestion-sensitive freight costs.
5. Clear a local crude market between producer and refiner roles using simple scarcity heuristics.
6. Convert crude into refined products using fixed yield vectors.
7. Allow a DPA-style intervention to shift US refining output toward military fuel at the expense of civilian fuel.
8. Price local consumer fuel using a scarcity-sensitive heuristic.
9. Apply demand destruction when local price exceeds a household decile's willingness to pay.
10. Record per-node history for prices, inventories, decile survival, and intervention state.

## Commander Interventions
The MVP should support the following controls:
1. Block Strait of Hormuz: disables or sharply constrains relevant Middle East export edges
2. Enforce Russian Embargo: disables or sharply constrains Russian exports to Europe
3. Invoke Defense Production Act: shifts US refining yields toward military fuel
4. Execute SPR Drawdown: injects a user-selected amount of crude into US inventory as a one-shot action

## UI Requirements
The frontend should be a Streamlit dashboard with:
1. Sidebar controls for advancing the sim and applying interventions
2. Top-line metrics for US price, EU price, congestion level, and at least one strategic readiness metric
3. A multi-line price chart across nodes over time
4. A decile resilience chart showing which household tiers can still afford fuel
5. A text or badge readout translating price levels into sector stress
6. Optional inventory or readiness charts if space allows

## Data Requirements
The engine should rely only on data already in the repo or constants derived from it.

The most useful current inputs appear to be in `src/cleaned-data/core-data.csv`:
1. `oil_consumption_thousand_bpd_2024`
2. `oil_production_thousand_bpd_2024`
3. `refinery_capacity_thousand_bpd_2024`
4. `refinery_throughput_thousand_bpd_2024`
5. `gasoline_throughput_thousand_bpd_approx`
6. `diesel_throughput_thousand_bpd_approx`
7. `jet_fuel_throughput_thousand_bpd_approx`
8. `gdp_per_capita_usd_2024`
9. `gini_coefficient_weighted_latest_wb`

The runtime engine should not need pandas or external services. Preprocessing can happen offline or in a tiny standard-library bootstrap step.

## Acceptance Criteria
1. Baseline scenario runs for at least 30 simulated days without errors.
2. A Hormuz shock produces delayed but visible price and affordability stress in at least one downstream node.
3. A Russian embargo materially worsens European conditions relative to baseline.
4. A DPA pivot improves military-relevant fuel availability while making civilian affordability worse in the US.
5. An SPR drawdown visibly cushions a US price spike or inventory shortfall.
6. The Streamlit app preserves engine state across button clicks.
7. The simulation is deterministic for a fixed starting state and intervention sequence.

## Deferred Roadmap
### Phase 2
1. Governments as decision-making agents
2. Capital allocators and investment dynamics
3. Monthly capex and capacity expansion decisions
4. Richer locality attributes such as tariffs, tax, and institutional instability
5. More geographic resolution
6. Information asymmetry, arbitrage, and speculative behavior

### Phase 3
1. Firm-level modeling
2. Multi-layer logistics networks
3. Counterparty negotiation and contracting
4. Scenario comparison and replay tooling

## Open Questions
1. Should the primary civilian stress metric be gasoline, diesel, or a blended civilian fuel index?
2. Should the fifth node represent China specifically or the broader Indo-Pacific demand basin?
3. Should military demand be an explicit demand bucket, or is tracking jet inventory/readiness enough for the MVP?
4. Should household willingness to pay be hand-tuned per node, or derived mechanically from GDP and inequality inputs?
5. Do you want the MVP positioned as a hackathon demo first, or as the first slice of the broader research architecture?
