import argparse
import os
import sys
import time

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from stations.models import Station


OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
HEADERS = {"User-Agent": "NaijaFuelFinder/1.0 (OpenStreetMap station importer)"}
DEFAULT_REQUEST_TIMEOUT = (15, 180)

# Approximate extent of Nigeria; the country-area filter in each query excludes
# fuel stations in neighbouring countries that fall inside this rectangle.
NIGERIA_BOUNDS = (4.2, 2.6, 14.0, 14.7)
REGION_HEIGHT = 2.0
REGION_WIDTH = 2.5
MIN_REGION_SIZE = 0.5


def region_boxes(bounds=NIGERIA_BOUNDS):
    south, west, north, east = bounds
    lat = south
    while lat < north:
        region_north = min(lat + REGION_HEIGHT, north)
        lon = west
        while lon < east:
            region_east = min(lon + REGION_WIDTH, east)
            yield (lat, lon, region_north, region_east)
            lon = region_east
        lat = region_north


def make_query(bounds):
    south, west, north, east = bounds
    return f"""
    [out:json][timeout:120];
    area["ISO3166-1"="NG"][admin_level=2]->.nigeria;
    (
      node["amenity"="fuel"](area.nigeria)({south},{west},{north},{east});
      way["amenity"="fuel"](area.nigeria)({south},{west},{north},{east});
      relation["amenity"="fuel"](area.nigeria)({south},{west},{north},{east});
    );
    out center;
    """


def fetch_region(bounds, session=None, request_timeout=DEFAULT_REQUEST_TIMEOUT):
    session = session or requests
    query = make_query(bounds)
    failures = []

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = session.post(
                endpoint,
                data={"data": query},
                headers=HEADERS,
                timeout=request_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(
                payload.get("elements"), list
            ):
                raise ValueError("Overpass response does not contain an elements list.")
            return payload["elements"]
        except (requests.RequestException, ValueError) as error:
            failures.append(f"{endpoint}: {error}")
            time.sleep(1)

    raise RuntimeError("; ".join(failures))


def fetch_region_with_subdivision(
    bounds,
    min_region_size=MIN_REGION_SIZE,
    request_timeout=DEFAULT_REQUEST_TIMEOUT,
):
    try:
        return fetch_region(bounds, request_timeout=request_timeout)
    except RuntimeError as error:
        south, west, north, east = bounds
        height = north - south
        width = east - west
        if height <= min_region_size and width <= min_region_size:
            raise

        mid_lat = (south + north) / 2
        mid_lon = (west + east) / 2
        smaller_regions = (
            (south, west, mid_lat, mid_lon),
            (south, mid_lon, mid_lat, east),
            (mid_lat, west, north, mid_lon),
            (mid_lat, mid_lon, north, east),
        )
        print(
            f"  Region timed out ({error}); retrying as "
            f"{len(smaller_regions)} smaller regions."
        )
        elements = []
        failures = []
        for smaller_region in smaller_regions:
            try:
                elements.extend(
                    fetch_region_with_subdivision(
                        smaller_region,
                        min_region_size,
                        request_timeout,
                    )
                )
            except RuntimeError as subregion_error:
                failures.append((smaller_region, subregion_error))

        if failures:
            details = "; ".join(
                f"{region}: {subregion_error}"
                for region, subregion_error in failures
            )
            raise RuntimeError(details)
        return elements


def station_from_element(element):
    tags = element.get("tags", {})
    center = element.get("center", {})
    lat = element.get("lat", center.get("lat"))
    lon = element.get("lon", center.get("lon"))
    if lat is None or lon is None:
        return None

    station_id = f"{element.get('type', 'element')}/{element.get('id', 'unknown')}"
    return {
        "name": str(
            tags.get("name") or tags.get("operator") or f"Fuel Station {station_id}"
        )[:255],
        "brand": str(tags.get("brand") or tags.get("operator") or "Independent")[:50],
        "latitude": lat,
        "longitude": lon,
        "state": str(tags.get("addr:state") or tags.get("addr:city") or "Unknown")[:50],
    }


def import_osm_stations(region_numbers=None, timeout_seconds=None):
    all_regions = list(region_boxes())
    if region_numbers is None:
        regions = all_regions
    else:
        invalid_regions = [
            number for number in region_numbers
            if number < 1 or number > len(all_regions)
        ]
        if invalid_regions:
            raise ValueError(
                f"Region numbers must be between 1 and {len(all_regions)}."
            )
        regions = [all_regions[number - 1] for number in region_numbers]

    request_timeout = (
        (min(15, timeout_seconds), timeout_seconds)
        if timeout_seconds is not None
        else DEFAULT_REQUEST_TIMEOUT
    )
    print(
        f"Fetching {len(regions)} of {len(all_regions)} Nigeria regions from "
        "OpenStreetMap. This may take several minutes."
    )

    existing_coordinates = {
        (round(float(latitude), 6), round(float(longitude), 6))
        for latitude, longitude in Station.objects.values_list("latitude", "longitude")
    }
    created_count = 0
    skipped_count = 0
    failed_regions = []

    for index, bounds in enumerate(regions, start=1):
        south, west, north, east = bounds
        print(
            f"[{index}/{len(regions)}] Fetching "
            f"{south:.1f},{west:.1f} to {north:.1f},{east:.1f}..."
        )
        try:
            elements = fetch_region_with_subdivision(
                bounds, request_timeout=request_timeout
            )
        except RuntimeError as error:
            failed_regions.append((bounds, str(error)))
            print("  All Overpass endpoints failed for this region; continuing.")
            continue

        new_stations = []
        for element in elements:
            station = station_from_element(element)
            if station is None:
                continue
            coordinate = (
                round(float(station["latitude"]), 6),
                round(float(station["longitude"]), 6),
            )
            if coordinate in existing_coordinates:
                skipped_count += 1
                continue
            existing_coordinates.add(coordinate)
            new_stations.append(Station(**station))

        if new_stations:
            Station.objects.bulk_create(new_stations, batch_size=500)
            created_count += len(new_stations)
        print(f"  Added {len(new_stations)} stations.")
        time.sleep(1)

    print(f"Added {created_count} new stations; skipped {skipped_count} duplicates.")
    if failed_regions:
        print(
            f"Import incomplete: {len(failed_regions)} of {len(regions)} regions "
            "could not be fetched. Stations from successful regions were saved."
        )
        for bounds, error in failed_regions:
            south, west, north, east = bounds
            print(f"  Failed region {south},{west},{north},{east}: {error}")
        return False

    print("Import complete.")
    return True


def parse_region_numbers(value):
    try:
        numbers = [int(item.strip()) for item in value.split(",")]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Regions must be comma-separated numbers, for example 4,7."
        ) from error
    if not numbers or any(number < 1 for number in numbers):
        raise argparse.ArgumentTypeError("Region numbers must be positive.")
    if len(set(numbers)) != len(numbers):
        raise argparse.ArgumentTypeError("Region numbers must not be repeated.")
    return numbers


def main():
    parser = argparse.ArgumentParser(
        description="Import fuel stations from OpenStreetMap's Overpass API."
    )
    parser.add_argument(
        "--regions",
        type=parse_region_numbers,
        help="Comma-separated region numbers to retry (1-25); defaults to all regions.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Per-endpoint read timeout in seconds (connect timeout is at most 15).",
    )
    args = parser.parse_args()
    if args.timeout is not None and args.timeout < 1:
        parser.error("--timeout must be a positive number of seconds.")

    if not import_osm_stations(args.regions, args.timeout):
        sys.exit(1)


if __name__ == "__main__":
    main()
