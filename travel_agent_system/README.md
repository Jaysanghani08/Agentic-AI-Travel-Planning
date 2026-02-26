# Travel Agent System

Multi-agent AI Travel System built with CrewAI for CLI usage.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys.
2. Install dependencies (from project root): `pip install -e .` or `crewai install` (if you have the CrewAI CLI).
3. Run from the CLI:
   - Default run: `crewai run`
   - Direct module run: `python -m travel_agent_system.run_crew`
   - Custom params example:
     `python -m travel_agent_system.run_crew --origin Delhi --destination Tokyo --style "Culture & Food" --budget 415000 --interests "Culture,Food" --approval "Approved"`

## Agents

- **Scout**: Researches local activities and hidden gems.
- **Logistician**: Fetches flight and hotel data via Amadeus.
- **Auditor**: Validates budget and itinerary feasibility.
- **Orchestrator**: Manages workflow and approval checkpoints.
