# Travel Agent System

Multi-agent AI Travel System built with CrewAI and Streamlit.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys.
2. Install dependencies (from project root): `pip install -e .` or `crewai install` (if you have the CrewAI CLI).
3. Run: `crewai run` or `python -m travel_agent_system.main`.

## Agents

- **Scout**: Researches local activities and hidden gems.
- **Logistician**: Fetches flight and hotel data via Amadeus.
- **Auditor**: Validates budget and itinerary feasibility.
- **Orchestrator**: Manages workflow and approval checkpoints.
