"""
Constants for the Travel Agent System.
Configurable/fixed values only; no business logic.
"""

# Common city names (and variants) to IATA airport/city codes for flight and hotel tools.
# When the user or task uses a city name, the agent can use this mapping to call tools with IATA codes.
CITY_TO_IATA: dict[str, str] = {
    "ahmedabad": "AMD",
    "mumbai": "BOM",
    "bombay": "BOM",
    "delhi": "DEL",
    "new delhi": "DEL",
    "dehradun": "DED",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "chennai": "MAA",
    "madras": "MAA",
    "hyderabad": "HYD",
    "kolkata": "CCU",
    "calcutta": "CCU",
    "kochi": "COK",
    "cochin": "COK",
    "pune": "PNQ",
    "goa": "GOI",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "chandigarh": "IXC",
    "new york": "NYC",
    "nyc": "NYC",
    "los angeles": "LAX",
    "lax": "LAX",
    "london": "LON",
    "paris": "PAR",
    "dubai": "DXB",
    "singapore": "SIN",
    "hong kong": "HKG",
    "tokyo": "TYO",
}
