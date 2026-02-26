"""Legacy package entrypoint that forwards to the CLI runner."""

from __future__ import annotations

from travel_agent_system.run_crew import main as run_cli


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
