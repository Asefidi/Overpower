# Introducing Overpower, an Agent Based Model of the Fossil Fuel Supply chain

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

## Future additions:
I can incorporate my behavioural model that simulates real financial thinking and the aggregate behaviours of analysts and speculators seeking higher returns.
greater geographic resolution
## VI. Conclusion: Overpower as a testing lab for economic strategy
Through bottom up aggregation of outcomes form Agent Based Models, Overpower gives DoD logisticians a dashboard to wargame supply shocks and test policy interventions, create a testing lab for strategic intervention and create much more accurate and effective forecasts that can inform decision dominance and secure outcomes before engagement.  