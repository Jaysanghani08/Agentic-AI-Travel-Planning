"""Entry point for the Travel Agent System crew."""

from travel_agent_system.crew import TravelAgentSystemCrew


def main() -> None:
    """Run the travel agent system crew with sample inputs."""
    crew = TravelAgentSystemCrew()
    result = crew.crew().kickoff(
        inputs={
            "destination": "Tokyo",
            "style": "culture and food",
            "budget": "5000 USD",
        }
    )
    print(result)


if __name__ == "__main__":
    main()
