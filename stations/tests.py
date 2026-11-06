import argparse
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase

from requests import HTTPError

from import_stations import (
    fetch_region,
    fetch_region_with_subdivision,
    import_osm_stations,
    parse_region_numbers,
    region_boxes,
    station_from_element,
)
from .models import PriceReport, Station


class StationImportHelpersTests(TestCase):
    def test_region_boxes_cover_nigeria_bounds_without_gaps(self):
        boxes = list(region_boxes())

        self.assertEqual(len(boxes), 25)
        self.assertEqual(boxes[0][:2], (4.2, 2.6))
        self.assertEqual(boxes[-1][2:], (14.0, 14.7))
        for first, second in zip(boxes, boxes[1:]):
            self.assertTrue(
                first[2] == second[0] or first[3] == second[1]
                or first[0] == second[2] or first[1] == second[3]
            )

    def test_parse_region_numbers_accepts_comma_separated_regions(self):
        self.assertEqual(parse_region_numbers("4, 7,25"), [4, 7, 25])

    def test_parse_region_numbers_rejects_repeated_regions(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_region_numbers("4,4")

    @patch("import_stations.time.sleep")
    @patch("import_stations.Station.objects.values_list", return_value=[])
    @patch("import_stations.fetch_region_with_subdivision", return_value=[])
    def test_import_can_retry_one_region_with_short_timeout(
        self, fetch_region_mock, _coordinates, _sleep
    ):
        import_osm_stations(region_numbers=[4], timeout_seconds=20)

        fetch_region_mock.assert_called_once_with(
            list(region_boxes())[3],
            request_timeout=(15, 20),
        )

    def test_station_from_element_uses_way_center(self):
        station = station_from_element({
            "type": "way",
            "id": 42,
            "center": {"lat": 5.5, "lon": 7.5},
            "tags": {"amenity": "fuel", "name": "Umuahia Fuel"},
        })

        self.assertEqual(station["name"], "Umuahia Fuel")
        self.assertEqual(station["latitude"], 5.5)
        self.assertEqual(station["longitude"], 7.5)

    @patch("import_stations.time.sleep")
    def test_fetch_region_tries_next_endpoint_after_gateway_error(self, _sleep):
        response = Mock()
        response.json.return_value = {"elements": [{"type": "node", "id": 1}]}
        session = Mock()
        session.post.side_effect = [HTTPError("504"), response]

        elements = fetch_region((5.0, 7.0, 6.0, 8.0), session=session)

        self.assertEqual(elements, [{"type": "node", "id": 1}])
        self.assertEqual(session.post.call_count, 2)

    @patch("import_stations.fetch_region")
    def test_failed_region_is_retried_as_smaller_regions(self, fetch_region_mock):
        bounds = (4.0, 2.0, 6.0, 4.0)
        fetch_region_mock.side_effect = [
            RuntimeError("504"),
            [{"type": "node", "id": 1}],
            [{"type": "node", "id": 2}],
            [{"type": "node", "id": 3}],
            [{"type": "node", "id": 4}],
        ]

        elements = fetch_region_with_subdivision(bounds, min_region_size=0.5)

        self.assertEqual([element["id"] for element in elements], [1, 2, 3, 4])
        self.assertEqual(fetch_region_mock.call_count, 5)

    @patch("import_stations.fetch_region")
    def test_failed_smallest_region_is_reported(self, fetch_region_mock):
        fetch_region_mock.side_effect = RuntimeError("504")

        with self.assertRaisesRegex(RuntimeError, "504"):
            fetch_region_with_subdivision(
                (4.0, 2.0, 4.25, 2.25), min_region_size=0.5
            )

        fetch_region_mock.assert_called_once()


class NearbyStationsApiTests(TestCase):
    def setUp(self):
        self.nearby_station = Station.objects.create(
            name="Central Fuel",
            brand="NNPC",
            latitude=9.08,
            longitude=7.40,
            state="FCT",
        )
        self.far_station = Station.objects.create(
            name="Distant Fuel",
            brand="TOTAL",
            latitude=6.52,
            longitude=3.37,
            state="Lagos",
        )
        PriceReport.objects.create(
            station=self.nearby_station,
            fuel_type="PMS",
            price_per_liter=Decimal("950.00"),
            queue_status="SHORT",
        )
        PriceReport.objects.create(
            station=self.nearby_station,
            fuel_type="AGO",
            price_per_liter=Decimal("1100.00"),
        )

    def test_home_page_renders_openfreemap_map_container(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="map"')
        self.assertContains(response, "maplibre-gl@5.6.1")
        self.assertContains(response, "tiles.openfreemap.org/styles/liberty")

    def test_returns_nearby_stations_in_distance_order(self):
        response = self.client.get(
            "/api/stations/", {"lat": 9.0765, "lng": 7.3986, "radius": 10}
        )

        self.assertEqual(response.status_code, 200)
        stations = response.json()
        self.assertEqual([station["id"] for station in stations], [self.nearby_station.id])
        self.assertGreaterEqual(stations[0]["distance_km"], 0)

    def test_fuel_filter_uses_latest_report_for_that_fuel(self):
        response = self.client.get(
            "/api/stations/",
            {
                "lat": 9.0765,
                "lng": 7.3986,
                "radius": 10,
                "fuel_type": "PMS",
            },
        )

        station = response.json()[0]
        self.assertEqual(station["fuel_type"], "PMS")
        self.assertEqual(station["price"], "950.00")

    def test_nationwide_search_returns_stations_beyond_100_km(self):
        response = self.client.get(
            "/api/stations/",
            {"lat": 4.3, "lng": 2.8, "radius": "nearest"},
        )

        self.assertEqual(response.status_code, 200)
        station_ids = [station["id"] for station in response.json()]
        self.assertIn(self.far_station.id, station_ids)
        far_station = next(
            station for station in response.json()
            if station["id"] == self.far_station.id
        )
        self.assertGreater(far_station["distance_km"], 100)

    def test_nationwide_search_returns_only_ten_closest_stations(self):
        for index in range(11):
            Station.objects.create(
                name=f"Lagos Station {index}",
                brand="NNPC",
                latitude=6.52 + (index + 1) * 0.01,
                longitude=3.37,
                state="Lagos",
            )

        response = self.client.get(
            "/api/stations/",
            {"lat": 6.52, "lng": 3.37, "radius": "nearest"},
        )

        self.assertEqual(response.status_code, 200)
        stations = response.json()
        self.assertEqual(len(stations), 10)
        distances = [station["distance_km"] for station in stations]
        self.assertEqual(distances, sorted(distances))
        self.assertEqual(stations[0]["id"], self.far_station.id)

    def test_rejects_missing_or_out_of_range_coordinates(self):
        missing_coordinates = self.client.get("/api/stations/")
        invalid_coordinates = self.client.get(
            "/api/stations/", {"lat": "NaN", "lng": 7.4}
        )

        self.assertEqual(missing_coordinates.status_code, 400)
        self.assertEqual(invalid_coordinates.status_code, 400)

    def test_rejects_invalid_radius_and_fuel_type(self):
        invalid_radius = self.client.get(
            "/api/stations/", {"lat": 9, "lng": 7, "radius": 500}
        )
        invalid_fuel = self.client.get(
            "/api/stations/",
            {"lat": 9, "lng": 7, "fuel_type": "JET"},
        )

        self.assertEqual(invalid_radius.status_code, 400)
        self.assertEqual(invalid_fuel.status_code, 400)

    def test_rejects_invalid_search_mode(self):
        response = self.client.get(
            "/api/stations/",
            {"lat": 9, "lng": 7, "radius": "everywhere"},
        )

        self.assertEqual(response.status_code, 400)


class SubmitPriceReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="driver", password="test-pass")
        self.station = Station.objects.create(
            name="Central Fuel",
            brand="NNPC",
            latitude=9.08,
            longitude=7.40,
            state="FCT",
        )

    def submit_report(self, **overrides):
        payload = {
            "station_id": self.station.id,
            "fuel_type": "PMS",
            "price": "950.00",
            "queue_status": "NONE",
            "is_available": True,
        }
        payload.update(overrides)
        return self.client.post(
            "/api/report/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_requires_login(self):
        response = self.submit_report()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(PriceReport.objects.count(), 0)

    def test_authenticated_user_can_submit_report(self):
        self.client.force_login(self.user)

        response = self.submit_report()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PriceReport.objects.get().station, self.station)
        self.assertEqual(PriceReport.objects.get().reporter, self.user)

    def test_rejects_invalid_price_without_saving_report(self):
        self.client.force_login(self.user)

        response = self.submit_report(price="5000")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PriceReport.objects.count(), 0)

    def test_rejects_duplicate_user_report(self):
        self.client.force_login(self.user)
        self.submit_report()

        response = self.submit_report()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PriceReport.objects.count(), 1)

    def test_rejects_malformed_json(self):
        self.client.force_login(self.user)

        response = self.client.post(
            "/api/report/", data="{", content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            "/api/report/",
            data=json.dumps(
                {
                    "station_id": self.station.id,
                    "fuel_type": "PMS",
                    "price": "950.00",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
