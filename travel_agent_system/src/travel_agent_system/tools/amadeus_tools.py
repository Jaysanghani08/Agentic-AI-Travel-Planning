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
"""

import os
from typing import Optional

from amadeus import Client
from amadeus import Hotel as AmadeusHotel
from amadeus.client.errors import ResponseError
from crewai.tools import tool
from dotenv import load_dotenv

load_dotenv()

# Approximate exchange rates to requested currency (base: USD). Update as needed.
CURRENCY_RATES_FROM_USD = {
    "USD": 1.0,
    "EUR": 0.92,
    "INR": 83.0,
    "GBP": 0.79,
    "JPY": 149.0,
}

DATA_NOT_FOUND_MSG = "DATA_NOT_FOUND: No real-world options available for these constraints."


def _convert_currency(amount: float, from_currency: str, to_currency: str) -> float:
    """Convert amount from one currency to another using approximate rates (USD as pivot)."""
    from_currency = (from_currency or "USD").upper()
    to_currency = (to_currency or "USD").upper()
    if from_currency == to_currency:
        return round(amount, 2)
    usd_per_from = 1.0 / (CURRENCY_RATES_FROM_USD.get(from_currency) or 1.0)
    to_per_usd = CURRENCY_RATES_FROM_USD.get(to_currency) or 1.0
    return round(amount * usd_per_from * to_per_usd, 2)


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
        """
        Search flights and return a structured string: price (in requested currency),
        airline, and a direct booking-ready link. Returns DATA_NOT_FOUND if no offers.
        """
        try:
            response = self._client.shopping.flight_offers_search.get(
                originLocationCode=origin.upper(),
                destinationLocationCode=destination.upper(),
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

        lines = []
        for i, offer in enumerate(offers[:10], 1):
            price_info = offer.get("price") or {}
            total = price_info.get("total") or "0"
            try:
                total_f = float(total)
            except (TypeError, ValueError):
                total_f = 0.0
            from_cur = (price_info.get("currency") or "USD").upper()
            total_converted = _convert_currency(total_f, from_cur, currency)

            segments = offer.get("itineraries", [{}])[0].get("segments", [])
            carrier = ""
            if segments:
                first = segments[0]
                carrier_code = first.get("carrierCode") or ""
                operating = first.get("operating", {}) or {}
                carrier = operating.get("carrierCode") or carrier_code

            # Booking-ready link: Google Flights search so user can complete booking
            booking_link = (
                f"https://www.google.com/travel/flights?"
                f"q=Flights%20to%20{destination}%20from%20{origin}%20on%20{date}"
            )
            lines.append(
                f"{i}. Price: {total_converted} {currency} | Airline: {carrier} | "
                f"Book: {booking_link}"
            )

        return "\n".join(lines) if lines else DATA_NOT_FOUND_MSG

    def hotel_search(
        self,
        city_code: str,
        travel_style: str = "",
        currency: str = "USD",
    ) -> str:
        """
        Search hotels by city code (IATA). Filters by travel_style when possible
        (e.g. hostels for backpackers). Returns DATA_NOT_FOUND if no properties.
        """
        try:
            response = self._client.reference_data.locations.hotel.get(
                keyword=city_code.upper(),
                subType=[AmadeusHotel.HOTEL_LEISURE, AmadeusHotel.HOTEL_GDS],
            )
        except ResponseError:
            return DATA_NOT_FOUND_MSG

        data = getattr(response, "data", None) or getattr(response, "result", None)
        if not data:
            return DATA_NOT_FOUND_MSG

        if isinstance(data, list):
            hotels = data
        elif isinstance(data, dict):
            hotels = data.get("data", []) or []
        else:
            hotels = []
        if not hotels:
            return DATA_NOT_FOUND_MSG

        # Optional filter by travel_style (e.g. hostel, budget, backpacker)
        style_lower = (travel_style or "").lower()
        if any(kw in style_lower for kw in ("backpack", "hostel", "budget")):
            filtered = [
                h for h in hotels
                if h.get("name") and any(
                    x in (h.get("name") or "").lower()
                    for x in ("hostel", "budget", "backpacker", "inn")
                )
            ]
            if not filtered:
                filtered = hotels  # fallback to all if no keyword match
        else:
            filtered = hotels

        lines = []
        for i, h in enumerate(filtered[:15], 1):
            name = h.get("name") or h.get("hotelId") or "Hotel"
            addr = (h.get("address") or {}).get("lines", [])
            address = (addr[0] if addr else "") or ""
            lines.append(f"{i}. {name} | {address}")

        return "\n".join(lines) if lines else DATA_NOT_FOUND_MSG

    def activity_search(
        self,
        latitude: float,
        longitude: float,
        currency: str = "USD",
    ) -> str:
        """
        Find top-rated points of interest (activities) at the given lat/long.
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


# Singleton used by @tool functions so they can access the client
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
) -> str:
    """
    Search for flights from origin to destination on the given date.
    Returns structured options with price (in requested currency), airline, and booking link.
    Use IATA codes (e.g. DEL, BOM, NYC). Date format: YYYY-MM-DD.
    """
    return _get_amadeus_tools().flight_search(
        origin=origin,
        destination=destination,
        date=date,
        currency=currency.upper(),
    )


@tool("Hotel Search")
def hotel_search_tool(
    city_code: str,
    travel_style: str = "",
    currency: str = "USD",
) -> str:
    """
    Search for hotels in a city by IATA city code.
    Filters by travel_style when relevant (e.g. hostels for backpackers).
    """
    return _get_amadeus_tools().hotel_search(
        city_code=city_code,
        travel_style=travel_style,
        currency=currency.upper(),
    )


@tool("Activity / Points of Interest Search")
def activity_search_tool(
    latitude: float,
    longitude: float,
    currency: str = "USD",
) -> str:
    """
    Find top-rated activities (points of interest) at the given coordinates.
    Use latitude and longitude (e.g. 35.6762, 139.6503 for Tokyo).
    """
    return _get_amadeus_tools().activity_search(
        latitude=latitude,
        longitude=longitude,
        currency=currency.upper(),
    )
