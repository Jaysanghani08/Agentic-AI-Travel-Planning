"""CLI entry point for running the Travel Agent System crew end-to-end."""

from __future__ import annotations

import argparse


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_crew",
        description="Run the Travel Agent System from the command line.",
    )
    parser.add_argument("--origin", default="Delhi", help="Trip origin (city or airport code).")
    parser.add_argument("--destination", default="Tokyo", help="Trip destination.")
    parser.add_argument("--style", default="Culture & Food", help="Travel style.")
    parser.add_argument("--budget", type=float, default=415000, help="Budget amount.")
    parser.add_argument(
        "--interests",
        default="Culture,Food",
        help="Comma-separated interests (example: Culture,Food,Nightlife).",
    )
    parser.add_argument(
        "--approval",
        default="Approved",
        help="Approval/feedback text passed to logistics stage.",
    )
    return parser.parse_args()


def main() -> None:
    from travel_agent_system.crew import TravelAgentSystemCrew

    args = _parse_args()
    interest_list = [item.strip() for item in args.interests.split(",") if item.strip()]
    interests = ", ".join(interest_list) if interest_list else "General"
    budget_str = f"{args.budget:.0f} INR"

    user_input = (
        f"Trip to {args.destination} from {args.origin}, {args.style}, "
        f"budget {budget_str}, interests: {interests}"
    )

    crew = TravelAgentSystemCrew()
    print("Running Scout phase...")
    scout_result = crew.scout_crew().kickoff(
        inputs={
            "user_input": user_input,
            "destination": args.destination,
            "style": args.style,
            "budget": budget_str,
        }
    )
    shortlist_output = str(scout_result.raw) if hasattr(scout_result, "raw") else str(scout_result)
    print("\n--- Scout shortlist ---")
    print(shortlist_output)

    print("\nRunning Logistics + Audit phase...")
    final_result = crew.logistics_crew().kickoff(
        inputs={
            "shortlist_from_scout": shortlist_output,
            "human_approval": args.approval,
            "destination": args.destination,
            "style": args.style,
            "budget": budget_str,
        }
    )

    print("\n--- Final itinerary output ---")
    print(final_result.raw if hasattr(final_result, "raw") else final_result)


if __name__ == "__main__":
    main()
