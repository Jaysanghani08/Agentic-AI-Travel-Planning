"""CLI entry point for running the Travel Agent System crew end-to-end."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from crewai import Crew, Process


REQUIRED_FIELDS = (
    "origin",
    "destination",
    "start_date",
    "end_date",
    "num_people",
    "budget",
    "style",
    "interests",
)

HITL_PROMPTS = {
    "origin": "Enter trip origin (city or airport code): ",
    "destination": "Enter destination (city or airport code): ",
    "start_date": "Enter start date (e.g., 2026-03-01): ",
    "end_date": "Enter end date (e.g., 2026-03-05): ",
    "num_people": "Enter number of people: ",
    "budget": "Enter budget per person with currency (e.g., 20000 INR): ",
    "style": "Enter travel style (e.g., budget, luxury, culture, adventure): ",
    "interests": "Enter interests (comma-separated): ",
}

MISSING_SENTINELS = {"", "none", "null", "n/a", "na", "unknown", "not provided"}

# Keywords that indicate the audit flagged a budget failure.
_AUDIT_FAIL_KEYWORDS = (
    "fail",
    "infeasible",
    "exceeds budget",
    "over budget",
    "cannot be met",
    "budget alert",
    "budget notification",
    "critical budget",
    "not feasible",
)

# Currency symbol → ISO code mapping for budget parsing.
_CURRENCY_SYMBOL_MAP: dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "₩": "KRW",
    "₺": "TRY",
    "₫": "VND",
    "฿": "THB",
    "د.إ": "AED",
    "S$": "SGD",
}


def _raw_to_text(result: Any) -> str:
    return str(result.raw) if hasattr(result, "raw") else str(result)


def _markdown_to_plain(text: str) -> str:
    """Convert common markdown to plain text for copy-friendly terminal output.

    Handles bold/italic, headers, horizontal rules, and markdown tables
    (converted to fixed-width columns).
    """
    if not text:
        return text
    out = text
    # Strip bold/italic: **x** or *x* -> x; _x_ only when not part of a word
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"\*(.+?)\*", r"\1", out)
    out = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", out)
    out = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"\1", out)
    # Strip atx headers: ### Title -> Title
    out = re.sub(r"^#{1,6}\s+", "", out, flags=re.MULTILINE)
    # Horizontal rule --- to newline
    out = re.sub(r"\n-{3,}\s*\n", "\n\n", out)
    # Convert markdown tables to fixed-width plain text
    out = _markdown_tables_to_plain(out)
    # Normalize multiple newlines to at most two
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _markdown_tables_to_plain(text: str) -> str:
    """Detect markdown table blocks and convert them to fixed-width plain text."""
    lines = text.split("\n")
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" in line and line.strip().count("|") >= 2:
            table_lines: list[str] = [line]
            j = i + 1
            while j < len(lines) and "|" in lines[j]:
                table_lines.append(lines[j])
                j += 1
            rows: list[list[str]] = []
            for tline in table_lines:
                cells = [c.strip() for c in tline.split("|")]
                if cells and cells[0] == "":
                    cells = cells[1:]
                if cells and cells[-1] == "":
                    cells = cells[:-1]
                if cells and all(re.match(r"^[-:\s]+$", cell) for cell in cells):
                    continue
                if cells:
                    rows.append(cells)
            if rows:
                ncols = max(len(r) for r in rows)
                widths = [0] * ncols
                for row in rows:
                    for c, cell in enumerate(row):
                        if c < ncols:
                            widths[c] = max(widths[c], len(cell))
                for row in rows:
                    padded = []
                    for c, cell in enumerate(row):
                        if c < ncols:
                            padded.append(cell.ljust(widths[c]))
                    result.append("  ".join(padded))
                result.append("")
            else:
                result.extend(table_lines)
            i = j
            continue
        result.append(line)
        i += 1
    return "\n".join(result)


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


def _to_int_people(value: Any) -> int | None:
    """Parse a positive integer for number of people."""
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


def _parse_iso_date(value: Any) -> datetime | None:
    """Parse YYYY-MM-DD date string; returns None if invalid."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in MISSING_SENTINELS:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _days_between(start_str: str, end_str: str) -> int | None:
    """Compute number of days between start and end date (inclusive). Returns None if invalid."""
    start_dt = _parse_iso_date(start_str)
    end_dt = _parse_iso_date(end_str)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return None
    delta = (end_dt - start_dt).days + 1
    return delta if delta > 0 else None


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


def _extract_currency_from_budget(budget_str: str) -> str:
    """Extract the ISO currency code from a budget string like '15000 INR', '$500', '€200'.

    Checks symbol map first, then looks for a 3-letter uppercase code.
    Defaults to 'USD' if no currency can be identified.
    """
    if not budget_str:
        return "USD"
    # Check multi-char symbols first (longer matches take priority)
    for symbol, code in sorted(_CURRENCY_SYMBOL_MAP.items(), key=lambda x: -len(x[0])):
        if symbol in budget_str:
            return code
    # Match an explicit ISO code (3 uppercase letters, word boundary)
    code_match = re.search(r"\b([A-Z]{3})\b", budget_str.upper())
    if code_match:
        return code_match.group(1)
    return "USD"


def _validate_iso_date(value: str) -> bool:
    """Return True only when value is a valid YYYY-MM-DD date string."""
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _validate_budget_format(value: str) -> bool:
    """Return True when value contains at least one digit (i.e. looks like a budget amount)."""
    return bool(re.search(r"\d", value))


def _normalize_extracted_fields(extracted: dict[str, Any]) -> dict[str, str]:
    budget_val = extracted.get("budget")
    if not budget_val and (
        extracted.get("budget_amount") is not None or extracted.get("budget_currency")
    ):
        budget_val = {
            "amount": extracted.get("budget_amount"),
            "currency": extracted.get("budget_currency"),
        }

    dates_val = (
        extracted.get("start_or_dates")
        or extracted.get("travel_dates")
        or extracted.get("dates")
    )
    start_date_raw = extracted.get("start_date")
    end_date_raw = extracted.get("end_date")
    start_date = _clean_text_value(start_date_raw) if start_date_raw is not None else ""
    end_date = _clean_text_value(end_date_raw) if end_date_raw is not None else ""

    normalized = {
        "origin": _clean_text_value(extracted.get("origin", "")),
        "destination": _clean_text_value(extracted.get("destination", "")),
        "start_date": start_date,
        "end_date": end_date,
        "start_or_dates": _clean_text_value(dates_val),
        "days": "",
        "num_people": "",
        "budget": _normalize_budget(budget_val),
        "style": _clean_text_value(extracted.get("style", "")),
        "interests": _normalize_interests(extracted.get("interests")),
    }

    parsed_days = _to_int_days(extracted.get("days"))
    if parsed_days is not None:
        normalized["days"] = str(parsed_days)
    elif start_date and end_date:
        derived = _days_between(start_date, end_date)
        if derived is not None:
            normalized["days"] = str(derived)

    parsed_people = _to_int_people(
        extracted.get("num_people") or extracted.get("number_of_people")
    )
    if parsed_people is not None:
        normalized["num_people"] = str(parsed_people)

    if start_date and end_date and not normalized["start_or_dates"]:
        normalized["start_or_dates"] = f"{start_date} to {end_date}"

    return normalized


def _build_user_input(prompt: str, fields: dict[str, str]) -> str:
    travel_dates = fields.get("start_or_dates") or (
        f"{fields['start_date']} to {fields['end_date']}"
        if fields.get("start_date") and fields.get("end_date")
        else ""
    )
    return (
        f"{prompt.strip()}\n"
        f"Origin: {fields['origin']}\n"
        f"Destination: {fields['destination']}\n"
        f"Start date: {fields['start_date']}\n"
        f"End date: {fields['end_date']}\n"
        f"Travel dates/start: {travel_dates}\n"
        f"Number of days: {fields['days']}\n"
        f"Number of people: {fields['num_people']}\n"
        f"Budget: {fields['budget']}\n"
        f"Style: {fields['style']}\n"
        f"Interests: {fields['interests']}"
    )


def _collect_missing_fields(fields: dict[str, str]) -> None:
    """Prompt the user for any required fields that are missing or invalid.

    Validates date format (YYYY-MM-DD) for start/end date fields.
    Validates that budget contains a numeric amount.
    Loops until all fields are valid.
    """
    while True:
        missing = [name for name in REQUIRED_FIELDS if _is_missing_value(fields.get(name, ""))]
        if not missing:
            return

        print("\nNeed more information to continue.")
        for field_name in missing:
            while True:
                value = input(HITL_PROMPTS[field_name]).strip()

                if field_name == "num_people":
                    parsed = _to_int_people(value)
                    if parsed is None:
                        print("Please enter a valid positive number for number of people.")
                        continue
                    fields[field_name] = str(parsed)
                    break

                if field_name in ("start_date", "end_date"):
                    if _is_missing_value(value):
                        print("This field is required.")
                        continue
                    if not _validate_iso_date(value):
                        print("Please enter a valid date in YYYY-MM-DD format (e.g. 2026-03-15).")
                        continue
                    fields[field_name] = value[:10]
                    break

                if field_name == "budget":
                    if _is_missing_value(value):
                        print("This field is required.")
                        continue
                    if not _validate_budget_format(value):
                        print(
                            "Please enter a budget with a numeric amount "
                            "(e.g. '20000 INR' or '$500')."
                        )
                        continue
                    fields[field_name] = value
                    break

                if _is_missing_value(value):
                    print("This field is required.")
                    continue
                fields[field_name] = value
                break


def _audit_suggests_fail(audit_text: str) -> bool:
    """Return True when the audit report contains budget-failure language."""
    lower = audit_text.lower()
    return any(keyword in lower for keyword in _AUDIT_FAIL_KEYWORDS)


def main() -> None:
    from travel_agent_system.crew import TravelAgentSystemCrew

    raw_prompt = input("Describe your travel request: ").strip()
    while not raw_prompt:
        print("Prompt is required.")
        raw_prompt = input("Describe your travel request: ").strip()

    crew = TravelAgentSystemCrew()

    # Intent extraction: run silently (verbose=False) — this is a background parsing step.
    extraction_result = Crew(
        agents=[crew.orchestrator()],
        tasks=[crew.intent_analysis()],
        process=Process.sequential,
        verbose=False,
    ).kickoff(inputs={"user_input": raw_prompt})

    extracted_text = _raw_to_text(extraction_result)
    extracted_json = _extract_json_block(extracted_text)
    fields = _normalize_extracted_fields(extracted_json)

    _collect_missing_fields(fields)

    # Derive days from start_date/end_date (no user prompt for days).
    if fields.get("start_date") and fields.get("end_date"):
        d = _days_between(fields["start_date"], fields["end_date"])
        fields["days"] = str(d) if d is not None else ""
    else:
        fields["days"] = ""

    # Derive nights: last day is return travel, so accommodation nights = days - 1.
    if fields.get("days"):
        try:
            days_int = int(fields["days"])
            nights_val = max(days_int - 1, 0)
            fields["nights"] = str(nights_val) if nights_val > 0 else ""
        except ValueError:
            fields["nights"] = ""
    else:
        fields["nights"] = ""

    # Ensure travel_dates string for downstream tasks.
    if not fields.get("start_or_dates") and fields.get("start_date") and fields.get("end_date"):
        fields["start_or_dates"] = f"{fields['start_date']} to {fields['end_date']}"

    # Extract currency from budget string so tools receive the correct unit.
    fields["currency"] = _extract_currency_from_budget(fields.get("budget", ""))

    user_input = _build_user_input(raw_prompt, fields)

    print("\nRunning Scout phase...")
    scout_result = crew.scout_crew().kickoff(
        inputs={
            "user_input": user_input,
            "origin": fields["origin"],
            "destination": fields["destination"],
            "start_date": fields["start_date"],
            "end_date": fields["end_date"],
            "travel_dates": fields["start_or_dates"],
            "days": fields["days"],
            "nights": fields.get("nights", ""),
            "num_people": fields["num_people"],
            "style": fields["style"],
            "budget": fields["budget"],
            "currency": fields["currency"],
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
    logistics_inputs: dict[str, str] = {
        "shortlist_from_scout": shortlist_output,
        "human_approval": approval,
        "previous_final_plan": "",  # Empty on first run; set when implementing refinement loop
        "origin": fields["origin"],
        "destination": fields["destination"],
        "start_date": fields["start_date"],
        "end_date": fields["end_date"],
        "travel_dates": fields["start_or_dates"],
        "days": fields["days"],
        "nights": fields.get("nights", ""),
        "num_people": fields["num_people"],
        "style": fields["style"],
        "budget": fields["budget"],
        "currency": fields["currency"],
        "interests": fields["interests"],
    }

    logistics_result = crew.logistics_only_crew(verbose=False).kickoff(inputs=logistics_inputs)
    logistics_text = _raw_to_text(logistics_result)

    audit_result = crew.audit_only_crew(verbose=False).kickoff(
        inputs={
            **logistics_inputs,
            "logistics_plan_from_previous_step": logistics_text,
        }
    )
    audit_text = _raw_to_text(audit_result)

    print("\n--- Logistics plan ---")
    print(_markdown_to_plain(logistics_text))
    print("\n--- Audit ---")
    print(_markdown_to_plain(audit_text))

    # If the audit flagged a budget failure, ask the user before proceeding.
    if _audit_suggests_fail(audit_text):
        print(
            "\n⚠  Budget Alert: The audit indicates the estimated trip cost exceeds your budget."
        )
        while True:
            choice = (
                input(
                    "Would you like to (1) continue and generate the itinerary anyway, "
                    "or (2) exit to adjust your budget/dates? Enter 1 or 2: "
                )
                .strip()
                .lower()
            )
            if choice in ("1", "continue", "yes", "y"):
                break
            if choice in ("2", "exit", "no", "n", "quit"):
                print(
                    "\nExiting. Please re-run with an adjusted budget, shorter dates, "
                    "or a different destination."
                )
                return
            print("Please enter 1 to continue or 2 to exit.")

    itinerary_result = crew.itinerary_crew(verbose=False).kickoff(
        inputs={
            **logistics_inputs,
            "logistics_plan_from_previous_step": logistics_text,
            "audit_report_from_previous_step": audit_text,
        }
    )
    itinerary_text = _raw_to_text(itinerary_result)

    print("\n--- Your Travel Itinerary ---")
    print(_markdown_to_plain(itinerary_text))


if __name__ == "__main__":
    main()
