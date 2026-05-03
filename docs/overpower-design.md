# Overpower MVP Technical Design

## Design Principles
1. realistic: this project attempts to create a realistic agent based model of the fuel supply chain
2. Non-Linear: This project attempts to model real market clearing mechanisms and model the effects of microdecisions on macro outcomes
3. each step of the supply chain should have a market clearing mechanism based on bidding and MWTP of the bidding agents.
4. MWTP of refiner agent should be based on 
5. each region is a node in the graph, with edges representing time it takes for a tanker to go from one region to another, there should be a blockade
6. there should be a blockade and supply disruption mechanism for every edge allowing the user interface to artificially cut an edge or hike up shipping costs by a set multiplier.
7. for every edge, there should be 

## regions (nodes)
NORTHCOM
CHINA
EUCOM
RUSSIA
IRAN
INDOPACOM
CENTCOM
AFRICOM
SOUTHCOM

## edges
NORTHCOM is connected to EUCOM, INDOPACOM, AFRICOM, CENTCOM 
CHINA is connected to NORTHCOM, CENTCOM, AFRICOM, SOUTHCOM, RUSSIA, IRAN
EUCOM is connected to CENTCOM, AFRICOM, INDOPACOM, SOUTHCOM
RUSSIA is connected to IRAN, INDOPACOM, CENTCOM, AFRICOM
CENTCOM is connected to INDOPACOM, AFRICOM

## region Attributes:
   fear_multiplier (based on panic, can be affected by blockade and disruption mechanism)
   associated agents and whatever, idk figure this out yourself. 

## edges attributes
   adjusted by the interface

## agents
50 agents representing the top 20 largest global oil refiners and 30 aggregate agents representing smaller refineries.
representing the top 50

50 agents representing the top 20 largest crude oil wells by ownership and 30 aggregate agents representing smaller wells
give each nation 5 stochastic demand functions representing five industrial sectors each with their own MWTP curves competing for gasoline, diesel, jet fuel:
   heavy logistics (shipping)
   aviation
   agriculture
   light logistics (rail, last mile trucking, etc)
other (construction, transportation, mining, etc)
assign each sector its own MWTP curve, create a heuristic for estimating it per region
create 4 household functions per region representing each income quartile, base their MWTP on GDP per capita adjusted for GINI

use @cleaned-data to create the crude and refinery agents
use GDP data 

## not modeled:
currency dynamics, inflationary and recessionary gaps. 
disregard all refining output except gasoline, jet fuel, diesel.


## Edge Schema
Each transit edge is a crude route with latency based on time to transport and transportation cost per thousand gallons:




## `step()` Pipeline
each step in the model should represent a week of activity, and be executable by click of button on the interface managing the agent behaviours in that given step.


