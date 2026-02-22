"""
Streamlit frontend for the AI Travel System: sidebar, map, metrics, HITL, itinerary export.
Run with: streamlit run travel_agent_system/main.py (from project root) or
          streamlit run src/travel_agent_system/main.py
"""

from __future__ import annotations

import json
from io import BytesIO
import streamlit as st
from streamlit_folium import st_folium

# Day-wise colors for map markers
DAY_COLORS = [
    "#1f77b4", "#2ca02c", "#ff7f0e", "#d62728", "#9467bd",
]

TRAVEL_STYLES = ["", "Solo", "Family", "Couple", "Business", "Adventure", "Culture & Food", "Budget", "Luxury"]
INTEREST_OPTIONS = ["Culture", "Food", "Adventure", "Nature", "Nightlife", "Shopping", "History", "Photography"]


def _ensure_session_state() -> None:
    if "awaiting_shortlist_approval" not in st.session_state:
        st.session_state.awaiting_shortlist_approval = False
    if "plan_ready" not in st.session_state:
        st.session_state.plan_ready = False
    if "shortlist_data" not in st.session_state:
        st.session_state.shortlist_data = []
    if "human_feedback" not in st.session_state:
        st.session_state.human_feedback = ""
    if "scout_feedback_log" not in st.session_state:
        st.session_state.scout_feedback_log = []
    if "crew_raw_output" not in st.session_state:
        st.session_state.crew_raw_output = ""
    if "scout_shortlist_output" not in st.session_state:
        st.session_state.scout_shortlist_output = ""


def render_sidebar(
    destination: str,
    origin: str,
    budget_inr: float,
    travel_style: str,
    interests: list[str],
) -> bool:
    """Build sidebar with inputs and Plan My Trip button. Returns True if Plan was clicked."""
    with st.sidebar:
        st.header("Trip parameters")
        dest = st.text_input("Destination", value=destination, key="sidebar_dest")
        orig = st.text_input("Origin", value=origin, key="sidebar_origin")
        budget = st.number_input("Budget (INR)", min_value=0, value=int(budget_inr), step=5000, key="sidebar_budget")
        style = st.selectbox("Travel Style", TRAVEL_STYLES, index=TRAVEL_STYLES.index(travel_style) if travel_style in TRAVEL_STYLES else 0, key="sidebar_style")
        interest_list = st.multiselect("Interests", INTEREST_OPTIONS, default=interests, key="sidebar_interests")

        st.divider()
        plan_clicked = st.button("Plan My Trip", type="primary", width="stretch")
        if plan_clicked:
            st.session_state.sidebar_params = {
                "destination": dest,
                "origin": orig,
                "budget_inr": float(budget),
                "travel_style": style,
                "interests": interest_list,
            }
        st.caption("Human-in-the-loop: you’ll approve the activity shortlist before logistics run.")
    return plan_clicked


def plot_map_day_colored(places: list[dict]) -> None:
    """Render a folium map with day-wise color-coded markers (Day 1 = Blue, Day 2 = Green, etc.)."""
    import folium

    if not places:
        st.info("No locations to display. Run “Plan My Trip” and approve the shortlist.")
        return

    lat0 = places[0]["lat"]
    lon0 = places[0]["lon"]
    m = folium.Map(location=[lat0, lon0], zoom_start=12, tiles="OpenStreetMap")

    for p in places:
        day = p.get("day", 1)
        color = DAY_COLORS[(day - 1) % len(DAY_COLORS)]
        name = p.get("name", "Location")
        kind = p.get("type", "activity")
        folium.CircleMarker(
            [p["lat"], p["lon"]],
            radius=10,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(f"<b>Day {day}</b> – {name}<br>({kind})", max_width=200),
            tooltip=f"Day {day}: {name}",
        ).add_to(m)

    st_folium(m, use_container_width=True, key="itinerary_map")


def render_metrics(budget_inr: float, metrics: dict | None = None) -> None:
    """Total Cost, Remaining Budget, Confidence Score in columns. If metrics is None, shows placeholder."""
    c1, c2, c3 = st.columns(3)
    if metrics:
        with c1:
            st.metric("Total Cost (INR)", f"₹{metrics.get('total_cost_inr', 0):,.0f}")
        with c2:
            st.metric("Remaining Budget (INR)", f"₹{metrics.get('remaining_inr', budget_inr):,.0f}")
        with c3:
            st.metric("Confidence Score", f"{metrics.get('confidence_score', 0):.0%}")
    else:
        with c1:
            st.metric("Total Cost (INR)", "—")
        with c2:
            st.metric("Remaining Budget (INR)", f"₹{budget_inr:,.0f}")
        with c3:
            st.metric("Confidence Score", "—")
        st.caption("Metrics will appear in crew output above when available.")


def render_reasoning_log(entries: list[str]) -> None:
    """Agent Reasoning Log in an expander (Auditor transparency)."""
    with st.expander("Agent Reasoning Log (Auditor)", expanded=False):
        for i, line in enumerate(entries, 1):
            st.markdown(f"{i}. {line}")
        if not entries:
            st.caption("No reasoning entries yet.")


def _run_logistics_crew(
    shortlist_markdown: str,
    human_approval: str,
    destination: str,
    origin: str,
    budget_inr: float,
    travel_style: str,
) -> None:
    """Run logistics + audit crew and store result in session_state.crew_raw_output."""
    try:
        from travel_agent_system.crew import TravelAgentSystemCrew
        crew = TravelAgentSystemCrew()
        result = crew.logistics_crew().kickoff(inputs={
            "shortlist_from_scout": shortlist_markdown,
            "human_approval": human_approval,
            "destination": destination,
            "style": travel_style,
            "budget": f"{budget_inr} INR",
        })
        st.session_state.crew_raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
    except Exception as e:
        st.error(f"Logistics run failed: {e}")
        st.session_state.crew_raw_output = ""


def _render_hitl_shortlist_ui(
    shortlist_markdown: str,
    destination: str,
    origin: str,
    budget_inr: float,
    travel_style: str,
) -> None:
    """Show Scout shortlist in UI and Approve / Feedback buttons. Runs logistics crew on Approve or with feedback."""
    st.subheader("Activity shortlist – your approval")
    st.caption("Review the Scout's shortlist below. Approve to continue to logistics and audit, or send feedback so the plan reflects your requests.")
    if shortlist_markdown:
        st.markdown(shortlist_markdown)
    else:
        st.info("No shortlist output yet.")
    st.divider()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        approve = st.button("Approve Shortlist", type="primary", key="hitl_approve")
    with col_b:
        feedback = st.text_input(
            "Or send feedback (logistics will use this context)",
            key="hitl_feedback",
            placeholder="e.g. Prefer budget hotels, add one more food experience",
        )
        send_feedback = st.button("Send feedback & continue", key="hitl_send_feedback")

    if approve:
        _run_logistics_crew(
            shortlist_markdown=shortlist_markdown,
            human_approval="Approved",
            destination=destination,
            origin=origin,
            budget_inr=budget_inr,
            travel_style=travel_style,
        )
        st.session_state.awaiting_shortlist_approval = False
        st.session_state.plan_ready = True
        st.rerun()

    if send_feedback and feedback.strip():
        _run_logistics_crew(
            shortlist_markdown=shortlist_markdown,
            human_approval="User feedback: " + feedback.strip(),
            destination=destination,
            origin=origin,
            budget_inr=budget_inr,
            travel_style=travel_style,
        )
        st.session_state.scout_feedback_log.append(feedback.strip())
        st.session_state.awaiting_shortlist_approval = False
        st.session_state.plan_ready = True
        st.rerun()


def render_hitl_shortlist(shortlist: list[dict]) -> None:
    """Show shortlist and Approve / Feedback UI for human-in-the-loop."""
    st.subheader("Activity shortlist – your approval")
    st.caption("Review the Scout’s shortlist. Approve to continue to logistics, or send feedback for the Scout to re-run.")
    for i, item in enumerate(shortlist, 1):
        st.markdown(f"**{i}. {item.get('name', 'Activity')}**")
        st.caption(item.get("description", "") + f" — *{item.get('source', '')}*")
    st.divider()
    col_a, col_b = st.columns([1, 2])
    with col_a:
        approve = st.button("Approve Shortlist", type="primary", key="hitl_approve")
    with col_b:
        feedback = st.text_input("Or send feedback for Scout to re-run", key="hitl_feedback", placeholder="e.g. Add one more food tour")
        send_feedback = st.button("Send feedback", key="hitl_send_feedback")
    if approve:
        st.session_state.awaiting_shortlist_approval = False
        st.session_state.plan_ready = True
        st.session_state.human_feedback = "Approved"
        st.rerun()
    if send_feedback and feedback:
        st.session_state.scout_feedback_log.append(feedback)
        st.session_state.human_feedback = feedback
        st.info("Feedback recorded. Scout will re-run with: " + feedback)
        st.rerun()


def render_itinerary_and_export(
    itinerary: list[dict],
    budget_inr: float,
    destination: str,
    origin: str,
    crew_raw_output: str = "",
) -> None:
    """Day-by-day plan (dataframe + markdown) when available, and Download JSON / PDF from crew output."""
    st.subheader("Final itinerary")
    if itinerary:
        import pandas as pd
        df = pd.DataFrame(itinerary)
        cols = [c for c in ["day", "date", "type", "title", "details", "booking_url"] if c in df.columns]
        if cols:
            st.dataframe(df[cols], width="stretch", hide_index=True)
        st.markdown("**Day-by-day plan with links**")
        for row in itinerary:
            link = f"[Book]({row['booking_url']})" if row.get("booking_url") else "—"
            st.markdown(f"- **Day {row['day']}** ({row.get('date', '')}) — {row.get('title', '')}: {row.get('details', '')} {link}")
    else:
        st.info("Structured itinerary not available. See crew output above for the full plan.")

    st.divider()
    # Export uses user params + crew output (no mock)
    full = {
        "destination": destination,
        "origin": origin,
        "budget_inr": budget_inr,
        "crew_output": crew_raw_output,
        "itinerary": itinerary,
        "reasoning_log": [],
    }
    json_bytes = json.dumps(full, indent=2).encode("utf-8")
    st.download_button(
        "Download Itinerary (JSON)",
        data=json_bytes,
        file_name="itinerary.json",
        mime="application/json",
        key="dl_json",
    )
    pdf_bytes = _generate_itinerary_pdf(full)
    if pdf_bytes:
        st.download_button(
            "Download Itinerary (PDF)",
            data=pdf_bytes,
            file_name="itinerary.pdf",
            mime="application/pdf",
            key="dl_pdf",
        )


def _generate_itinerary_pdf(data: dict) -> bytes | None:
    """Simple PDF of itinerary and crew output using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph("Travel Itinerary", styles["Title"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Destination: {data.get('destination', '')} | Origin: {data.get('origin', '')} | Budget: ₹{data.get('budget_inr', 0):,.0f}", styles["Normal"]))
        story.append(Spacer(1, 16))
        story.append(Paragraph("Itinerary", styles["Heading2"]))
        rows = [["Day", "Date", "Type", "Title", "Details"]]
        for row in data.get("itinerary", []):
            rows.append([str(row.get("day", "")), row.get("date", ""), row.get("type", ""), row.get("title", ""), row.get("details", "")])
        t = Table(rows)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), "#eee"), ("GRID", (0, 0), (-1, -1), 0.5, "#ccc")]))
        story.append(t)
        story.append(Spacer(1, 16))
        story.append(Paragraph("Crew output", styles["Heading2"]))
        crew_out = (data.get("crew_output") or "")[:8000]  # limit length for PDF
        # Escape for ReportLab Paragraph (XML-style)
        crew_out = crew_out.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        story.append(Paragraph(crew_out or "No output.", styles["Normal"]))
        doc.build(story)
        return buffer.getvalue()
    except Exception:
        return None


def main() -> None:
    _ensure_session_state()
    params = st.session_state.get("sidebar_params") or {
        "destination": "",
        "origin": "",
        "budget_inr": 0.0,
        "travel_style": "",
        "interests": [],
    }
    destination = params["destination"]
    origin = params["origin"]
    budget_inr = params["budget_inr"]
    travel_style = params["travel_style"]
    interests = params.get("interests") or []

    plan_clicked = render_sidebar(destination, origin, budget_inr, travel_style, interests)
    if plan_clicked:
        # Phase 1: Run Scout only to get shortlist (no terminal prompt)
        submitted = st.session_state.get("sidebar_params") or params
        dest = submitted["destination"]
        orig = submitted["origin"]
        budget = float(submitted["budget_inr"])
        style = submitted["travel_style"]
        interest_list = submitted.get("interests") or []
        try:
            from travel_agent_system.crew import TravelAgentSystemCrew
            user_input = f"Trip to {dest} from {orig}, {style}, budget {budget} INR, interests: {', '.join(interest_list)}"
            crew = TravelAgentSystemCrew()
            scout_result = crew.scout_crew().kickoff(inputs={
                "user_input": user_input,
                "destination": dest,
                "style": style,
                "budget": f"{budget} INR",
            })
            st.session_state.scout_shortlist_output = str(scout_result.raw) if hasattr(scout_result, "raw") else str(scout_result)
            st.session_state.awaiting_shortlist_approval = True
            st.session_state.plan_ready = False
        except Exception as e:
            st.error(f"Scout run failed: {e}")
        st.rerun()

    st.title("AI Travel System")
    st.caption("Plan your trip with Scout, Logistician, Auditor, and Orchestrator agents.")

    if st.session_state.awaiting_shortlist_approval:
        _render_hitl_shortlist_ui(
            shortlist_markdown=st.session_state.get("scout_shortlist_output") or "",
            destination=destination,
            origin=origin,
            budget_inr=budget_inr,
            travel_style=travel_style,
        )
        st.stop()

    if not st.session_state.plan_ready:
        st.info("Set your trip parameters in the sidebar and click **Plan My Trip** to run the crew.")
        st.stop()

    # Full dashboard after crew run: show crew output and export from user params
    raw_output = st.session_state.get("crew_raw_output") or ""
    scout_output = st.session_state.get("scout_shortlist_output") or ""

    if raw_output:
        st.subheader("Crew output")
        st.markdown(raw_output)
    else:
        st.info("No crew output yet. Click **Plan My Trip** to run the crew.")

    # Allow going back to shortlist to approve again or give more feedback
    if scout_output:
        st.divider()
        if st.button("Back to shortlist – approve again or send more feedback", key="back_to_shortlist"):
            st.session_state.awaiting_shortlist_approval = True
            st.session_state.plan_ready = False
            st.rerun()

    render_metrics(budget_inr, metrics=None)
    with st.expander("Agent Reasoning Log (Auditor)"):
        st.caption("Reasoning is included in the crew output above.")
    st.subheader("Visual itinerary (day-wise)")
    plot_map_day_colored([])
    render_itinerary_and_export(
        itinerary=[],
        budget_inr=budget_inr,
        destination=destination,
        origin=origin,
        crew_raw_output=raw_output,
    )


if __name__ == "__main__":
    main()
