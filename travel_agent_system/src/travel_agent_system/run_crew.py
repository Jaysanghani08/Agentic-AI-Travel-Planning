"""CLI entry point for running the Travel Agent System crew end-to-end."""

from __future__ import annotations

import json
import re
from typing import Any

from crewai import Crew, Process


REQUIRED_FIELDS = (
    "origin",
    "destination",
    "start_or_dates",
    "days",
    "budget",
    "style",
    "interests",
)

HITL_PROMPTS = {
    "origin": "Enter trip origin (city or airport code): ",
    "destination": "Enter destination (city or airport code): ",
    "start_or_dates": "Enter travel dates or start date (e.g., 2026-03-01 to 2026-03-03): ",
    "days": "Enter number of days for the trip: ",
    "budget": "Enter budget with currency (e.g., 50000 INR): ",
    "style": "Enter travel style (e.g., budget, luxury, culture, adventure): ",
    "interests": "Enter interests (comma-separated): ",
}

MISSING_SENTINELS = {"", "none", "null", "n/a", "na", "unknown", "not provided"}


def _raw_to_text(result: Any) -> str:
    return str(result.raw) if hasattr(result, "raw") else str(result)


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced_match:
        cleaned = fenced_match.group(1)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    candidates = re.findall(r"\{.*?\}", cleaned, flags=re.DOTALL)
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _to_int_days(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    match = re.search(r"\d+", text)
    if not match:
        return None
    parsed = int(match.group(0))
    return parsed if parsed > 0 else None


def _clean_text_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in MISSING_SENTINELS else text


def _is_missing_value(value: str) -> bool:
    return not value.strip() or value.strip().lower() in MISSING_SENTINELS


def _normalize_interests(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        items = [_clean_text_value(item) for item in value]
        items = [item for item in items if item]
        return ", ".join(items)
    return _clean_text_value(value)


def _normalize_budget(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        amount = value.get("amount")
        currency = value.get("currency")
        if amount is not None and currency:
            cleaned = f"{amount} {currency}".strip()
            return _clean_text_value(cleaned)
        if amount is not None:
            return _clean_text_value(amount)
    return _clean_text_value(value)


def _normalize_extracted_fields(extracted: dict[str, Any]) -> dict[str, str]:
    budget_val = extracted.get("budget")
    if not budget_val and (
        extracted.get("budget_amount") is not None or extracted.get("budget_currency")
    ):
        budget_val = {
            "amount": extracted.get("budget_amount"),
            "currency": extracted.get("budget_currency"),
        }

    dates_val = extracted.get("start_or_dates") or extracted.get("travel_dates") or extracted.get("dates")

    normalized = {
        "origin": _clean_text_value(extracted.get("origin", "")),
        "destination": _clean_text_value(extracted.get("destination", "")),
        "start_or_dates": _clean_text_value(dates_val),
        "days": "",
        "budget": _normalize_budget(budget_val),
        "style": _clean_text_value(extracted.get("style", "")),
        "interests": _normalize_interests(extracted.get("interests")),
    }

    parsed_days = _to_int_days(extracted.get("days"))
    if parsed_days is not None:
        normalized["days"] = str(parsed_days)
    return normalized


def _build_user_input(prompt: str, fields: dict[str, str]) -> str:
    return (
        f"{prompt.strip()}\n"
        f"Origin: {fields['origin']}\n"
        f"Destination: {fields['destination']}\n"
        f"Travel dates/start: {fields['start_or_dates']}\n"
        f"Number of days: {fields['days']}\n"
        f"Budget: {fields['budget']}\n"
        f"Style: {fields['style']}\n"
        f"Interests: {fields['interests']}"
    )


def _collect_missing_fields(fields: dict[str, str]) -> None:
    while True:
        missing = [name for name in REQUIRED_FIELDS if _is_missing_value(fields.get(name, ""))]
        if not missing:
            return

        print("\nNeed more information to continue.")
        for field_name in missing:
            while True:
                value = input(HITL_PROMPTS[field_name]).strip()
                if field_name == "days":
                    parsed = _to_int_days(value)
                    if parsed is None:
                        print("Please enter a valid positive number for days.")
                        continue
                    fields[field_name] = str(parsed)
                    break
                if _is_missing_value(value):
                    print("This field is required.")
                    continue
                fields[field_name] = value
                break


def main() -> None:
    from travel_agent_system.crew import TravelAgentSystemCrew

    raw_prompt = input("Describe your travel request: ").strip()
    while not raw_prompt:
        print("Prompt is required.")
        raw_prompt = input("Describe your travel request: ").strip()

    crew = TravelAgentSystemCrew()
    extraction_result = Crew(
        agents=[crew.orchestrator()],
        tasks=[crew.intent_analysis()],
        process=Process.sequential,
        verbose=True,
    ).kickoff(inputs={"user_input": raw_prompt})

    extracted_text = _raw_to_text(extraction_result)
    extracted_json = _extract_json_block(extracted_text)
    fields = _normalize_extracted_fields(extracted_json)

    _collect_missing_fields(fields)
    user_input = _build_user_input(raw_prompt, fields)

    print("\nRunning Scout phase...")
    scout_result = crew.scout_crew().kickoff(
        inputs={
            "user_input": user_input,
            "origin": fields["origin"],
            "destination": fields["destination"],
            "travel_dates": fields["start_or_dates"],
            "days": fields["days"],
            "style": fields["style"],
            "budget": fields["budget"],
            "interests": fields["interests"],
        }
    )
    shortlist_output = _raw_to_text(scout_result)
    print("\n--- Scout shortlist ---")
    print(shortlist_output)

    approval = input(
        "\nEnter your approval or feedback for the shortlist (required before logistics): "
    ).strip()
    while not approval:
        print("Approval/feedback is required.")
        approval = input(
            "Enter your approval or feedback for the shortlist (required before logistics): "
        ).strip()

    print("\nRunning Logistics + Audit phase...")
    final_result = crew.logistics_crew().kickoff(
        inputs={
            "shortlist_from_scout": shortlist_output,
            "human_approval": approval,
            "origin": fields["origin"],
            "destination": fields["destination"],
            "travel_dates": fields["start_or_dates"],
            "days": fields["days"],
            "style": fields["style"],
            "budget": fields["budget"],
            "interests": fields["interests"],
        }
    )

    print("\n--- Final itinerary output ---")
    print(_raw_to_text(final_result))


if __name__ == "__main__":
    main()
