import json

import requests

from config import settings


def search_places(api_key, address):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName",
    }
    payload = {
        "textQuery": address,
        "regionCode": "HK",
        "locationRestriction": {
            "rectangle": {
                "low": {"latitude": 22.1193, "longitude": 113.8196},
                "high": {"latitude": 22.5597, "longitude": 114.4345},
            }
        },
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    return response.json()


def search_hk_location(address: str) -> dict:
    """
    Search the location of the address in Hong Kong using Google Places API.
    If the user's query contains an address, use the search_hk_location to search for the latitude and longitude of the address. You can use the latitude and longitude to search for geographic data in the database.
    Args:
        address (str): The address to search for.
    Returns:
        dict: The latitude and longitude of the address.
        example:
        {
            "latitude": 22.3193,
            "longitude": 114.1696
        }
    """
    result = search_places(settings.google_places_api_key, address)
    display_name = result["places"][0]["displayName"]["text"]
    params = {
        "address": display_name,
        "components": "country:HK",
        "key": settings.google_places_api_key,
    }
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    response = requests.get(url, params=params)
    location = response.json()["results"][0]["geometry"]["location"]

    return {
        "latitude": location["lat"],
        "longitude": location["lng"],
    }


if __name__ == "__main__":
    result = search_hk_location("Tsing Yi")
    print(result)
