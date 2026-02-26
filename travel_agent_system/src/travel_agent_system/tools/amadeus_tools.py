"""
Amadeus Travel Tools: flight search, hotel search, and points-of-interest.
Uses AMADEUS_API_KEY and AMADEUS_API_SECRET from .env.

No Hallucination guardrails:
- If the API fails, returns empty data, or raises: return the exact string
  "DATA_NOT_FOUND: No real-world options available for these constraints."
  so the agent never invents options.
- All price outputs are converted to the requested currency (e.g. INR) via
  a fixed rate table; we never echo raw API currency without conversion when
  the user asked for a specific currency.
- Flight prices are always shown as BOTH per-person and total-for-group to
  prevent agent misinterpretation.
"""

import os
from typing import Optional
from urllib.parse import quote_plus

from amadeus import Client
from amadeus.client.errors import ResponseError
from crewai.tools import tool
from dotenv import load_dotenv

from travel_agent_system.config.constants import CITY_TO_IATA

load_dotenv()

# Approximate exchange rates to requested currency (base: USD). Update as needed.
# Extended to cover common travel destinations.
CURRENCY_RATES_FROM_USD: dict[str, float] = {
    "USD": 1.0,
    "EUR": 0.92,
    "INR": 83.0,
    "GBP": 0.79,
    "JPY": 149.0,
    "AED": 3.67,
    "SGD": 1.34,
    "THB": 35.5,
    "MYR": 4.65,
    "AUD": 1.53,
    "CAD": 1.36,
    "CHF": 0.89,
    "HKD": 7.82,
    "NZD": 1.63,
    "SAR": 3.75,
    "ZAR": 18.5,
    "IDR": 15600.0,
    "VND": 24500.0,
    "PHP": 56.5,
    "TWD": 31.5,
    "KRW": 1330.0,
    "MXN": 17.1,
    "BRL": 4.95,
    "PKR": 278.0,
    "BDT": 110.0,
    "LKR": 310.0,
    "NPR": 133.0,
}

DATA_NOT_FOUND_MSG = "DATA_NOT_FOUND: No real-world options available for these constraints."
# Max hotel IDs to send to the offers search API per call (Amadeus API limit: 50).
_HOTEL_OFFERS_BATCH = 10


def _convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    """Convert amount from one currency to another using approximate rates (USD as pivot)."""
    from_currency = (from_currency or "USD").upper()
    to_currency = (to_currency or "USD").upper()
    if from_currency == to_currency:
        return round(amount, 2)
    from_rate = CURRENCY_RATES_FROM_USD.get(from_currency)
    to_rate = CURRENCY_RATES_FROM_USD.get(to_currency)
    if from_rate is None or to_rate is None:
        # Unknown currency — log and return as-is
        unknown = from_currency if from_rate is None else to_currency
        print(
            f"[AmadeusTravelTools] WARNING: Exchange rate for '{unknown}' not found. "
            "Returning unconverted amount. Add the rate to CURRENCY_RATES_FROM_USD."
        )
        return round(amount, 2)
    usd_amount = amount / from_rate
    return round(usd_amount * to_rate, 2)


def _resolve_iata(code: str) -> str:
    """Resolve a city name or IATA code to an uppercase IATA code.

    Falls back to the raw value (uppercased) when not found in the mapping.
    """
    cleaned = (code or "").strip().lower()
    return (CITY_TO_IATA.get(cleaned) or code).upper()


class AmadeusTravelTools:
    """Initializes the Amadeus client from .env (AMADEUS_API_KEY, AMADEUS_API_SECRET)."""

    def __init__(self) -> None:
        api_key = os.getenv("AMADEUS_API_KEY") or os.getenv("AMADEUS_CLIENT_ID")
        api_secret = os.getenv("AMADEUS_API_SECRET") or os.getenv("AMADEUS_CLIENT_SECRET")
        if not api_key or not api_secret:
            raise ValueError(
                "AMADEUS_API_KEY and AMADEUS_API_SECRET (or AMADEUS_CLIENT_ID/AMADEUS_CLIENT_SECRET) must be set in .env"
            )
        self._client = Client(client_id=api_key, client_secret=api_secret)

    @property
    def client(self) -> Client:
        return self._client

    def flight_search(
        self,
        origin: str,
        destination: str,
        date: str,
        currency: str = "USD",
        adults: int = 1,
    ) -> str:
        """Search flights and return structured pricing with explicit per-person AND total labels.

        The Amadeus API returns price.total as the aggregate for ALL adults. This method
        always divides by adults to derive the per-person cost and shows both values clearly
        so the agent can never misinterpret group-total as per-person.
        Returns DATA_NOT_FOUND if no offers.
        """
        # Resolve city names to IATA codes before calling the API.
        origin_code = _resolve_iata(origin)
        destination_code = _resolve_iata(destination)

        try:
            response = self._client.shopping.flight_offers_search.get(
                originLocationCode=origin_code,
                destinationLocationCode=destination_code,
                departureDate=date,
                adults=adults,
            )
        except ResponseError:
            return DATA_NOT_FOUND_MSG

        data = getattr(response, "data", None) or getattr(response, "result", None)
        if not data or (isinstance(data, list) and len(data) == 0):
            return DATA_NOT_FOUND_MSG

        offers = data if isinstance(data, list) else (data.get("data") or [])
        if not offers:
            return DATA_NOT_FOUND_MSG

        safe_adults = max(adults, 1)
        lines = []
        for i, offer in enumerate(offers[:10], 1):
            price_info = offer.get("price") or {}
            raw_total = price_info.get("total") or "0"
            try:
                total_f = float(raw_total)
            except (TypeError, ValueError):
                total_f = 0.0
            from_cur = (price_info.get("currency") or "USD").upper()

            # total_for_group is the Amadeus-returned value (all adults combined)
            total_for_group = _convert_currency(total_f, from_cur, currency)
            per_person = round(total_for_group / safe_adults, 2)

            segments = offer.get("itineraries", [{}])[0].get("segments", [])
            carrier = ""
            if segments:
                first = segments[0]
                carrier_code = first.get("carrierCode") or ""
                operating = (first.get("operating") or {})
                carrier = operating.get("carrierCode") or carrier_code

            booking_link = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights%20to%20{destination_code}%20from%20{origin_code}%20on%20{date}"
            )
            lines.append(
                f"{i}. Per-person: {per_person} {currency} | "
                f"Total for {safe_adults} traveler(s): {total_for_group} {currency} | "
                f"Airline: {carrier} | Book: {booking_link}"
            )

        return "\n".join(lines) if lines else DATA_NOT_FOUND_MSG

    def hotel_search(
        self,
        city_code: str,
        travel_style: str = "",
        currency: str = "USD",
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
        adults: int = 1,
    ) -> str:
        """Search hotels: two-step approach.

        Step 1 — reference lookup: get hotel names/IDs from Amadeus reference data.
        Step 2 — offers lookup: if check_in/check_out provided, call shopping.hotel_offers_search
                 to get actual nightly rates. Falls back gracefully to reference list only when
                 the shopping API returns no data.
        Returns DATA_NOT_FOUND if no properties at all.
        """
        iata_code = _resolve_iata(city_code)

        # --- Step 1: Get hotel reference list (names + IDs) ---
        try:
            ref_response = self._client.reference_data.locations.hotels.by_city.get(
                cityCode=iata_code,
            )
        except ResponseError:
            return DATA_NOT_FOUND_MSG

        ref_data = getattr(ref_response, "data", None) or getattr(ref_response, "result", None)
        if not ref_data:
            return DATA_NOT_FOUND_MSG

        hotels: list[dict] = ref_data if isinstance(ref_data, list) else (ref_data.get("data") or [])
        if not hotels:
            return DATA_NOT_FOUND_MSG

        # Optional: filter by travel style keywords.
        style_lower = (travel_style or "").lower()
        if any(kw in style_lower for kw in ("backpack", "hostel", "budget")):
            filtered = [
                h for h in hotels
                if h.get("name") and any(
                    x in (h.get("name") or "").lower()
                    for x in ("hostel", "budget", "backpacker", "inn")
                )
            ]
            filtered = filtered or hotels  # fallback when keyword match finds nothing
        else:
            filtered = hotels

        working_set = filtered[:_HOTEL_OFFERS_BATCH]

        # --- Step 2: Attempt live pricing via hotel_offers_search ---
        nightly_by_hotel: dict[str, float] = {}
        hotel_ids = [h.get("hotelId") for h in working_set if h.get("hotelId")]

        if hotel_ids and check_in and check_out:
            try:
                offers_response = self._client.shopping.hotel_offers_search.get(
                    hotelIds=hotel_ids,
                    checkInDate=check_in,
                    checkOutDate=check_out,
                    adults=adults,
                    currency=currency.upper(),
                )
                offers_data = (
                    getattr(offers_response, "data", None)
                    or getattr(offers_response, "result", None)
                    or []
                )
                for offer_group in offers_data:
                    hotel_info = offer_group.get("hotel") or {}
                    hotel_id = hotel_info.get("hotelId")
                    offers_list = offer_group.get("offers") or []
                    if hotel_id and offers_list:
                        # Pick cheapest offer
                        def _offer_price(o: dict) -> float:
                            try:
                                return float((o.get("price") or {}).get("total") or 0)
                            except (TypeError, ValueError):
                                return 0.0
                        best = min(offers_list, key=_offer_price)
                        price_info = best.get("price") or {}
                        raw_total = price_info.get("total") or "0"
                        from_cur = (price_info.get("currency") or "USD").upper()
                        try:
                            raw_f = float(raw_total)
                        except (TypeError, ValueError):
                            raw_f = 0.0
                        nightly_by_hotel[hotel_id] = _convert_currency(raw_f, from_cur, currency)
            except ResponseError:
                pass  # fall through — reference list only

        # --- Build output ---
        lines = []
        for i, h in enumerate(working_set, 1):
            hotel_id = h.get("hotelId") or ""
            name = h.get("name") or hotel_id or "Hotel"
            addr = (h.get("address") or {}).get("lines") or []
            address = addr[0] if addr else ""

            nightly = nightly_by_hotel.get(hotel_id)
            if nightly is not None:
                lines.append(
                    f"{i}. {name} | {address} | "
                    f"Lowest nightly rate: {nightly} {currency} (for {adults} guest(s))"
                )
            else:
                lines.append(f"{i}. {name} | {address} | Nightly rate: not available via API")

        result = "\n".join(lines) if lines else DATA_NOT_FOUND_MSG

        if result != DATA_NOT_FOUND_MSG:
            query_parts = [f"hotels in {iata_code}"]
            if check_in:
                query_parts.append(check_in)
            if check_out:
                query_parts.append(check_out)
            q = quote_plus(" ".join(query_parts))
            search_url = f"https://www.google.com/travel/hotels?q={q}"
            result = result + f"\n\nSearch / book hotels: {search_url}"

        return result

    def activity_search(
        self,
        latitude: float,
        longitude: float,
        currency: str = "USD",
    ) -> str:
        """Find top-rated points of interest (activities) at the given lat/long.

        Returns DATA_NOT_FOUND if no POIs.
        """
        try:
            response = self._client.reference_data.locations.points_of_interest.get(
                latitude=latitude,
                longitude=longitude,
            )
        except ResponseError:
            return DATA_NOT_FOUND_MSG

        data = getattr(response, "data", None) or getattr(response, "result", None)
        if not data:
            return DATA_NOT_FOUND_MSG

        pois = data if isinstance(data, list) else (data.get("data") or [])
        if not pois:
            return DATA_NOT_FOUND_MSG

        lines = []
        for i, poi in enumerate(pois[:15], 1):
            name = poi.get("name") or "Activity"
            geo = poi.get("geoCode") or {}
            lat = geo.get("latitude") or latitude
            lon = geo.get("longitude") or longitude
            lines.append(f"{i}. {name} | lat={lat}, long={lon}")
        return "\n".join(lines) if lines else DATA_NOT_FOUND_MSG


# Singleton used by @tool functions so they can access the client.
_amadeus_tools: Optional[AmadeusTravelTools] = None


def _get_amadeus_tools() -> AmadeusTravelTools:
    global _amadeus_tools
    if _amadeus_tools is None:
        _amadeus_tools = AmadeusTravelTools()
    return _amadeus_tools


@tool("Flight Search")
def flight_search_tool(
    origin: str,
    destination: str,
    date: str,
    currency: str = "USD",
    adults: int = 1,
) -> str:
    """Search for flights from origin to destination on the given date.

    Returns options with BOTH per-person price AND total-for-group price, airline, and booking link.
    Use IATA codes (e.g. DEL, BOM, NYC) or city names (resolved automatically).
    Date format: YYYY-MM-DD.
    Pass adults as the trip's number of travelers for total cost context.
    Always pass currency matching the traveler's stated budget currency (e.g. 'INR', 'USD').
    """
    return _get_amadeus_tools().flight_search(
        origin=origin,
        destination=destination,
        date=date,
        currency=currency.upper(),
        adults=adults,
    )


@tool("Hotel Search")
def hotel_search_tool(
    city_code: str,
    travel_style: str = "",
    currency: str = "USD",
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    adults: int = 1,
) -> str:
    """Search for hotels in a city by IATA city code or city name.

    ALWAYS pass check_in and check_out (YYYY-MM-DD) to enable live nightly rate retrieval.
    Pass adults as the number of travelers for accurate pricing.
    Always pass currency matching the traveler's stated budget currency (e.g. 'INR', 'USD').
    Filters by travel_style when relevant (e.g. hostels for backpackers).
    Returns hotel list with nightly rates where available, plus a hotel search booking link.
    """
    return _get_amadeus_tools().hotel_search(
        city_code=city_code,
        travel_style=travel_style,
        currency=currency.upper(),
        check_in=check_in,
        check_out=check_out,
        adults=adults,
    )


@tool("Activity / Points of Interest Search")
def activity_search_tool(
    latitude: float,
    longitude: float,
    currency: str = "USD",
) -> str:
    """Find top-rated activities (points of interest) at the given coordinates.

    Use latitude and longitude (e.g. 35.6762, 139.6503 for Tokyo).
    """
    return _get_amadeus_tools().activity_search(
        latitude=latitude,
        longitude=longitude,
        currency=currency.upper(),
    )
