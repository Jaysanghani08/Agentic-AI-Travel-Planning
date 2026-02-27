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

## Technical Explanation

### Framework and Tools Used

- **Framework**: CrewAI (agent orchestration and task execution).
- **Language/runtime**: Python CLI app.
- **External data provider**: Amadeus APIs via custom CrewAI tools.
- **Key libraries**:
  - `crewai[tools]` for multi-agent workflows.
  - `amadeus` for flights/hotels data.
  - `python-dotenv` for environment-based API credentials.
- **Configuration model**:
  - Agent roles/goals are defined in `src/travel_agent_system/config/agents.yaml`.
  - Task contracts and handoff expectations are defined in `src/travel_agent_system/config/tasks.yaml`.

### How Agents Collaborate and Share Context

The architecture uses a sequential, stage-based handoff model:

1. **Orchestrator** extracts structured fields from raw user input.
2. **Scout** generates a destination activity shortlist.
3. **Human checkpoint** collects approval/feedback before logistics.
4. **Logistician** sources flights/hotels based on approved shortlist.
5. **Auditor** validates budget and schedule feasibility.
6. **Orchestrator** composes the final day-by-day itinerary.

Context is explicitly passed between stages through structured kickoff inputs and prior-step outputs (for example `shortlist_from_scout`, `logistics_plan_from_previous_step`, and `audit_report_from_previous_step`). This keeps collaboration traceable and avoids hidden assumptions.

### Handling Real-Time Data (Flights, Weather, Availability)

- **Flights**: pulled from Amadeus flight offers search.
- **Hotels/availability**:
  - hotel reference discovery by destination,
  - then dated hotel offers search using check-in/check-out for live rates.
- **Currency handling**: prices are normalized to user currency for consistent budget checks.
- **No-hallucination guardrail**: when APIs fail or return no results, tools emit a strict `DATA_NOT_FOUND` response so agents do not invent options.
- **Weather**: not currently integrated in this version. Weather can be added by introducing a dedicated weather tool and passing its output into logistics/itinerary tasks.

### Budget Optimization Strategy

- Budget is captured per person, then evaluated as total group budget (`budget x num_people`).
- Logistician is prompted to balance cost and convenience while sourcing options.
- Auditor validates:
  - total cost vs budget (pass/fail),
  - timing realism and conflict checks,
  - accommodation-night consistency.
- If over-budget is detected, the CLI presents a budget alert and requires a user decision to proceed or exit and adjust constraints.
- Refinement loop supports iterative optimization without restarting from scratch.

### Why This Architecture

- **Separation of concerns**: each agent focuses on one domain (discovery, logistics, audit, orchestration).
- **Human-in-the-loop safety**: approval checkpoints reduce downstream planning drift.
- **Observability**: explicit handoffs make debugging and evaluation easier.
- **Extensibility**: new tools (weather, events, transport) can be added without redesigning the full workflow.
- **Practical reliability**: live API grounding plus audit checks improves trustworthiness of generated itineraries.
