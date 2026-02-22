"""
Headless entry point for running the Travel Agent System crew (no Streamlit).
Used by `crewai run` to avoid ScriptRunContext warnings and run the crew in the terminal.
For the Streamlit UI, use: streamlit run src/travel_agent_system/main.py
"""

from __future__ import annotations


def main() -> None:
    from travel_agent_system.crew import TravelAgentSystemCrew

    crew = TravelAgentSystemCrew()
    user_input = "Trip to Tokyo from Delhi, Culture & Food, budget 415000 INR, interests: Culture, Food"
    print("Running Travel Agent System crew (headless)...")
    result = crew.crew().kickoff(
        inputs={
            "user_input": user_input,
            "destination": "Tokyo",
            "style": "Culture & Food",
            "budget": "415000 INR",
        }
    )
    print("\n--- Crew output ---")
    print(result.raw if hasattr(result, "raw") else result)


if __name__ == "__main__":
    main()
