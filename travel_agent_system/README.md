# Travel Agent System

Multi-agent AI Travel System built with CrewAI for CLI usage.

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys.
2. Install dependencies (from project root): `pip install -e .` or `crewai install` (if you have the CrewAI CLI).
3. Run from the CLI:
   - Default run: `crewai run`
   - Direct module run: `python -m travel_agent_system.run_crew`

## Interactive Flow

- The CLI now starts by asking for a free-form prompt (example: `Build a travel plan for weekend trip`).
- The orchestrator uses LLM extraction to pull structured fields from your prompt.
- Required fields are:
  - origin
  - destination
  - travel dates or start date
  - number of days
  - budget (amount + currency)
  - style
  - interests
- If any required field is missing, the CLI asks follow-up questions until all are provided.
- After the scout shortlist is shown, approval/feedback is required before logistics + audit runs.
- After a final itinerary is generated, you can choose:
  - `refine`: modify the current itinerary directly (keeps current shortlist and trip inputs).
  - `update`: change core trip fields, then rerun Scout + Logistics.
  - `quit`: exit the planner.

## Agents

- **Scout**: Researches local activities and hidden gems.
- **Logistician**: Fetches flight and hotel data via Amadeus.
- **Auditor**: Validates budget and itinerary feasibility.
- **Orchestrator**: Manages workflow and approval checkpoints.
