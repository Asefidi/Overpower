# Introducing Overpower, an Agent Based Model of the Fossil Fuel Supply chain

## MVP Status
This repository now includes a runnable MVP built for a 10-hour hackathon sprint:

- A deterministic weekly simulation engine in `src/overpower/`
- A Streamlit dashboard in `app.py`
- Scenario presets fosr Hormuz pressure, Russia disruption, Venezuela outage, Taiwan Strait surge, Red Sea diversion, NATO winter diesel crunch, Gulf Coast hurricane, South China Sea blockade, and policy mitigation
- Military strategy overlays for steady state, ground combat operations, air-maritime campaigns, distributed island defense, rapid deployment surges, and humanitarian stability operations
- Route override controls, event logging, refinery rankings, shortage heatmaps, and a Strategic Readiness Index

The MVP uses 50 crude producer agents, 50 refinery agents, 45 sector demand agents, 36 household demand agents, and 6 dedicated military fuel buyers across 9 command-aligned localities.

## Quick Start
1. Install dependencies:
   ```bash
   python3 -m pip install -r requirements.txt
   ```
2. Launch the dashboard:
   ```bash
   streamlit run app.py
   ```
3. Run the regression suite:
   ```bash
   python3 -m unittest discover -s tests -v
   ```

If `plotly` is not installed yet, the app still runs with Streamlit-native charts.

## 60-Second Demo Flow
1. Start in `Baseline` with `Steady State` strategy and click `Run 4 Weeks`.
2. Note the military jet/diesel fulfillment, `Global Shortage`, and `Avg Crude Price` cards.
3. Switch to `Taiwan Strait Surge` plus `Air-Maritime Campaign`, hit `Reset`, then `Run 4 Weeks`.
4. Watch pressured Pacific lanes on the route graph, rising crude prices, and the event log.
5. Add a reserve release, refinery subsidy, or military priority overlay, then run 4 more weeks to compare mitigation outcomes.

## MVP Design Notes
- Canonical nodes come from `src/raw-input-data/core-data.csv`.
- Crude agents and refinery agents are loaded from the cleaned 50-agent rollups and scaled to locality-level baseline totals.
- Governments and capital allocators are represented as policy controls, not autonomous agents.
- Crude shipments respect route latency and queue into future weeks.
- Product allocation clears within the current step, with route blockades and shipping costs still affecting who gets served.
- Scenarios model external supply-chain shocks; military strategy overlays model operational posture by changing military demand, bids, and jet/diesel readiness weights.
- The readiness metric is weighted toward military jet and diesel fulfillment, with the selected strategy deciding the jet/diesel balance.

## I. Executive Summary
America's national energy security is currently modeled using 20th-century econometric tools that prioritize smoothed averages of rational homogenous agents over the gritty complex and chaotic reality of supply chains. 
Overpower is a high-fidelity Agent-Based Model (ABM) designed to simulate the micro-decisions of every major firm in the fossil fuel supply chain and create a testing lab for economic strategy. 
By modeling the system from the bottom-up, we identify non-linear failure points that traditional models systematically ignore and create a clear interface for understanding strategic outcomes and adverserial actions.
## II: Background:
One of the primary weapons used by America's adversaries to destabilize American interests, extract concessions, and apply diplomatic force on our country and its allies has historically been the supply of fossil fuels.
As energy rich adversaries occupying geopolitical choke-points in the global energy supply, Russia and Iran have the strategic advantage of using Hormuz and cheap Russian oil as a bargaining chip to extract massive concessions from America and its allies.

This geopolitical choke-hold held by our adversaries is an intolerable vulnerability and leaves us exposed to an immense level of harm from hostile adversaries, necessitating better macroeconomic models to explain 

Econometric models aggregate millions of heterogeneous individuals into homogenous statistical averages, erasing the complex micro-level behaviors and information asymmetries that actually drive outcomes and missing small seemingly insignificant events with disastrous consequences for national security. 

## III: Introduction:
 Overpower is a simplified version of my primary research at the University of Toronto building a predictive semiconductor supply chain model. 
 Overpower attempts to model the supply chain for fuel from extraction to consumption.

Overpower Uses agent base heuristics to model the asymmetric information availability, consumption and investment decisions of every major firm and understand the aggregate effects of micro-decisions on the overall price and availability of fossil fuels for both civilian and military needs. 
Overpower attempts to forecast the second order effects of supply chain disruptions on both energy price and availability and prepare Department of War logisticians and combatant commanders for previously unforeseeable disruptions and ensure operational energy readiness and the resilience of contested logistics networks against adversarial gray-zone tactics.

## IV: Methodology:
Overpower will model four distinct types of agents: Capital Allocators, Households, Governments, and firms.
As a more limited and computationally light preview model, Each agent will be given a hardcoded marginal utility function to determine it's payoffs from engaging in a transaction and its marginal willingness to pay for the commodities modelled.
Each agent will be assigned a locality determining base conditions such as tax rate, input costs, trade restrictions, tariffs, institutional stability, risks, etc.  
Firm and capital allocator agents are free to interact with one another, negotiating prices, partnerships, and investment.
Information is asymmetrically distributed with built in arbitrage opportunities and the use of price signals to disseminate information through markets. 
Each agent will be given a "turn" to determine investment decisions for the following month with information from the current market state.


## V: Limitations
Due to the short timeframe given by the national security hackathon, and my lack of access to the high quality data-sources I typically have through my university,
I treated all crude as identical inputs and created only an approximation of a refinery's Nelson Complexity Index.
I used simple sigmoid demand heuristics to represent agent purchasing decisions with multipliers for fear and greed. This ignores the strategic financial decisionmaking firms engage in.
Furthermore I compressed all households for a specific region into 10 decile agents representing an income quartile for that region, their Willingness to Pay for oil, consumption decisions, etc. 
Assume fixed oil production and refining capacity.

## Data sourcing:
https://www.energyinst.org/statistical-review/home
https://www.acq.osd.mil/eie/ero/oe/index.html
gem idk i'll write this tomorrow.

## Future additions:
I can incorporate my behavioural model that simulates real financial thinking and the aggregate behaviours of analysts and speculators seeking higher returns.
greater geographic resolution
## VI. Conclusion: Overpower as a testing lab for economic strategy
Through bottom up aggregation of outcomes form Agent Based Models, Overpower gives DoD logisticians a dashboard to wargame supply shocks and test policy interventions, create a testing lab for strategic intervention and create much more accurate and effective forecasts that can inform decision dominance and secure outcomes before engagement.  
