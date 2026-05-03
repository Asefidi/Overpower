# Overpower MVP Technical Design

## Design Principles
1. realistic: this project attempts to create a realistic agent based model of the fuel supply chain
2. Non-Linear: This project attempts to model real market clearing mechanisms and model the effects of microdecisions on macro outcomes
3. assume flexible prices and output

## agents
represent each region's crude production as a singular profit maximizing agent.
represent each nation's refinery production as a singular profit maximizing agent with a specific storage capacity and a demand multiplier for crude fear determined based on time since shock and major changes in global price.
give each nation 5 firm agents representing five industrial sectors:
heavy logistics (shipping)
aviation
agriculture
light logistics (rail, last mile trucking, etc)
intialize a transportation agent 
other (construction, transportation, mining, etc)
assign each sector its own MWTP curve, create a heuristic for estimating it per region
create ten household agents per region representing each decile in a region, base their MWTP on GDP per capita, they exclusively consume gasoline, they are willing to spend 3% of their share of national output on fossil fuels per year, so 0.00008219178 of their share per day.



## not modeled:
currency dynamics, inflationary and recessionary gaps. 
disregard all refining output except gasoline, jet fuel, diesel. 
## Engine State Shape
Use a plain nested dictionary. A recommended top-level shape is:


Use one consistent internal volume unit. The cleanest choice is:
1. Flows in `thousand barrels per day` (`kbd`)
2. Inventories in `thousand barrels` (`kbbl`)
3. Prices in `USD per barrel-equivalent`

This matches the checked-in data more naturally than full raw barrel counts.

## Node Schema
Each node should contain the same structural fields:

```python
node = {
    "meta": {
        "label": "USNORTHCOM",
        "seed_row": "USNORTHCOM",
    },
    "producer": {
        "daily_extraction_kbd": 0.0,
        "crude_inventory_kbbl": 0.0,
        "max_storage_kbbl": 0.0,
        "base_cost_usd_bbl": 0.0,
    },
    "refiner": {
        "crude_inventory_kbbl": 0.0,
        "max_storage_kbbl": 0.0,
        "capacity_kbd": 0.0,
        "complexity_score": 1.0,
        "base_wtp_usd_bbl": 0.0,
        "yield_vector": {
            "civilian_fuel": 0.45,
            "jet_fuel": 0.10,
        },
        "dpa_yield_vector": {
            "civilian_fuel": 0.30,
            "jet_fuel": 0.25,
        },
    },
    "products": {
        "civilian_fuel_kbbl": 0.0,
        "jet_fuel_kbbl": 0.0,
    },
    "market": {
        "crude_ask_usd_bbl": 0.0,
        "crude_bid_usd_bbl": 0.0,
        "civilian_price_usd_bbl": 0.0,
        "jet_price_usd_bbl": 0.0,
    },
    "consumers": {
        "households": [],
        "industrial": {
            "daily_demand_kbbl": 0.0,
            "max_wtp_usd_bbl": 0.0,
        },
        "military": {
            "daily_jet_demand_kbbl": 0.0,
            "priority": 1.0,
        },
    },
    "outcomes": {
        "surviving_deciles": 10,
        "civilian_unmet_demand_kbbl": 0.0,
        "jet_cover_days": 0.0,
    },
}
```

The name `civilian_fuel` is deliberate. If you decide diesel matters more than gasoline for the demo, the schema does not need to change.

## Household Consumer Schema
Keep household agents as a list of dictionaries:

```python
household = {
    "decile": 1,
    "daily_demand_kbbl": 0.0,
    "max_wtp_usd_bbl": 0.0,
    "active": True,
}
```

Recommended initialization:
1. Split regional civilian demand across 10 deciles with each decile's MWTP curve based on each region's specific GDP per capita and GINI coefficient

## Edge Schema
Each transit edge is a crude route with latency based on time to transport and transportation cost per thousand gallons:


```python
edge = {
    "source": "USCENTCOM",
    "destination": "USEUCOM",
    "commodity": "crude",
    "max_capacity_kbd": 0.0,
    "base_freight_usd_bbl": 0.0,
    "transit_days": 14,
    "queue_kbbl": [0.0] * 14,
    "last_requested_kbd": 0.0,
    "last_shipped_kbd": 0.0,
    "last_freight_rate_usd_bbl": 0.0,
}
```

The queue is the important simplification. It makes latency visible without introducing a complicated transport solver.

## Initialization Strategy
Use the local CSVs only to seed a static baseline. At runtime the engine should operate on in-memory dictionaries.

Recommended data mapping from `src/cleaned-data/core-data.csv`:
1. `oil_production_thousand_bpd_2024` -> producer extraction rate
2. `refinery_capacity_thousand_bpd_2024` -> refiner max daily throughput
3. `refinery_throughput_thousand_bpd_2024` -> starting effective operating rate
4. `oil_consumption_thousand_bpd_2024` -> total civilian plus industrial demand baseline
5. Product throughput columns -> initial product mix
6. GDP and Gini -> optional later calibration of household WTP

Recommended node seed mapping:
1. `USNORTHCOM` -> `USNORTHCOM`
2. `USCENTCOM` -> closest available `USCENTCOM-IRAN` row unless replaced
3. `USEUCOM` -> `USEUCOM`
4. `RUSSIA` -> `USEUCOM-CIS`
5. `INDOPACOM` -> either `USINDOPACOM-CHINA` or `USINDOPACOM`

## `step()` Pipeline
Break the daily loop into explicit phases:

```python
def step(self, actions=None):
    self._apply_interventions(actions)
    self._produce_crude()
    self._advance_transit_queues()
    self._clear_crude_markets()
    self._refine_products()
    self._clear_product_markets()
    self._consume_products()
    self._record_history()
    self._increment_clock()
```

### Phase 1: Apply Interventions
Separate persistent toggles from one-shot actions:
1. Persistent: Hormuz block, Russian embargo, DPA
2. One-shot: SPR drawdown

Persistent toggles mutate edge capacities or yield vectors while active.
One-shot actions mutate inventory once, then reset themselves.

### Phase 2: Produce Crude
For each producer:
1. Add daily extraction to producer crude inventory
2. Clamp at max storage
3. Record overflow if you want a simple wasted-production metric

### Phase 3: Advance Transit Queues
For each edge:
1. Pop the first queue slot and deliver it to destination refiner crude inventory
2. Append a zero-valued slot to maintain queue length
3. Compute utilization and freight pricing for today's requested flow

Recommended congestion function:

```python
utilization = requested_kbd / max(edge["max_capacity_kbd"], 1.0)
freight_rate = base_freight * (1.0 + 4.0 * (utilization ** 5))
```

This is intentionally violent near capacity because the demo benefits from visible bottleneck behavior.

### Phase 4: Clear Crude Markets
Each destination refiner decides whether to buy imported crude based on:
1. days of crude cover
2. replacement need versus storage headroom
3. supplier ask price plus freight

Suggested heuristics:

```python
producer_fullness = inventory / max_storage
producer_ask = base_cost + ask_spike * (1.0 - producer_fullness)

days_of_cover = crude_inventory / max(capacity_kbd, 1.0)
panic = max(0.0, (target_cover_days - days_of_cover) / target_cover_days)
refiner_bid = base_wtp * (1.0 + panic_multiplier * (panic ** 2))
```

If `refiner_bid >= producer_ask + freight_rate`, execute a shipment up to the minimum of:
1. source available crude
2. destination storage headroom
3. route max capacity
4. destination desired volume

### Phase 5: Refine Products
For each node:
1. Process crude up to the lesser of crude inventory or refinery capacity
2. Choose the standard yield vector unless DPA is active for the US
3. Increase product inventories based on yield

Keep refinery logic deterministic and local. The objective is legibility, not refinery realism.

### Phase 6: Clear Product Markets
Set the local civilian fuel price using:
1. a replacement-cost anchor from crude acquisition cost
2. a scarcity multiplier based on days of product cover

Suggested structure:

```python
product_cover_days = civilian_fuel_inventory / max(total_civilian_demand_kbd, 1.0)
scarcity = max(0.0, (target_product_days - product_cover_days) / target_product_days)
civilian_price = base_price * (1.0 + scarcity_multiplier * (scarcity ** 2))
```

This can be refined later, but it is enough to generate visible demand destruction.

### Phase 7: Consume Products
Order matters here:
1. Satisfy military jet demand first if you want the DPA to feel meaningful
2. Satisfy industrial demand next
3. Evaluate each household decile against current local civilian price
4. If price exceeds decile WTP, that decile's demand drops to zero for the day
5. Record `surviving_deciles`

This phase is where the civilian pain becomes visible in the UI.

### Phase 8: Record History
At minimum, store:
1. day label
2. per-node civilian price
3. per-node surviving deciles
4. per-node crude and product inventories
5. one global congestion metric
6. one strategic readiness metric such as US jet cover days

## Intervention Design
Represent interventions as data, not scattered `if` statements.

Recommended pattern:

```python
actions = {
    "block_hormuz": True,
    "russian_embargo": False,
    "dpa": False,
    "spr_drawdown_kbbl": 5000.0,
}
```

The engine then maps these actions into state mutations in one place. This keeps the Streamlit layer thin and makes scenario replay easier.

## Streamlit Design
### Session State
Use:

```python
if "engine" not in st.session_state:
    st.session_state.engine = OverpowerEngine()
```

The app should mutate `st.session_state.engine` in place and re-render from `engine.state`.

### Layout
Recommended layout:
1. Sidebar:
   - `Advance 1 Day`
   - `Advance 7 Days`
   - toggle: Hormuz block
   - toggle: Russian embargo
   - toggle: DPA
   - slider/button: SPR drawdown
2. Top row:
   - US civilian price
   - EU civilian price
   - global congestion penalty
   - US strategic readiness or jet cover days
3. Main row:
   - multi-line civilian price chart by node
   - bar chart of surviving deciles for the selected node
4. Lower row:
   - inventory chart or table
   - text stress readout

### Text Readout
Map the local civilian price into qualitative status text. Keep it rule-based and obvious.

Example pattern:
1. nominal
2. strained
3. disrupted
4. collapse

If you later switch from gasoline to diesel, the text thresholds should move with the chosen civilian fuel metric.

## Testing Strategy
Minimum verification before demo:
1. Engine initializes without syntax or key errors
2. Baseline can step 30 days
3. Hormuz block causes downstream stress after latency, not instantly
4. Russian embargo hurts Europe more than the US
5. DPA increases US jet availability and reduces civilian fuel availability
6. SPR drawdown increases US crude inventory exactly once per action
7. History arrays remain length-consistent across steps

## Recommended Implementation Order
1. Fix and simplify `engine.py` until baseline stepping works
2. Lock the top-level state schema
3. Implement edge queues and crude movement
4. Implement refining and product pricing
5. Implement household demand destruction
6. Add intervention plumbing
7. Build the Streamlit dashboard
8. Tune numbers only after the interactions are visible

## Decisions That Need User Input Soon
1. Civilian fuel metric: gasoline, diesel, or blended index
2. Explicit military demand: yes or no
3. Node mapping for `INDOPACOM`
4. WTP calibration style: hand-tuned or formula-based
