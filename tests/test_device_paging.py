import json
import unittest
from unittest.mock import MagicMock, patch

from app import api, device_service, sqs
from app.apple_fetch import ResponseDto
from app.dtos import BeamerDevice, DeviceResponse, PaginationMeta


def make_device(name: str) -> BeamerDevice:
    return BeamerDevice(id=f"id-{name}", name=name, privateKey={"type": "Buffer", "data": [1] * 28})


def make_page(page: int, names: list[str], total: int, limit: int) -> DeviceResponse:
    page_count = -(-total // limit)
    return DeviceResponse(
        data=[make_device(name) for name in names],
        meta=PaginationMeta(total=total, page=page, limit=limit, pageCount=page_count),
    )


def fake_haystacks_api(pages: dict[int, list[str]], limit: int):
    total = sum(len(names) for names in pages.values())

    def fetch(url, headers=None, limit=limit, page=1):
        return make_page(page, pages.get(page, []), total, limit)

    return MagicMock(side_effect=fetch)


class FetchDevicesMetadataTest(unittest.TestCase):
    def test_requests_one_based_page_in_stable_order(self):
        response = MagicMock(status_code=200)
        response.json.return_value = make_page(2, ["A"], total=3, limit=2).model_dump()

        with patch.object(api.requestSession, "get", return_value=response) as get:
            api.fetch_devices_metadata_from_space_invader_api("http://api.test/haystacks", limit=2, page=2)

        self.assertEqual(get.call_args.kwargs["params"], {
            "limit": 2,
            "page": 2,
            "orderBy": "createdAt",
            "orderDirection": "ASC",
        })


class IterDevicePagesTest(unittest.TestCase):
    def test_fetches_every_page_until_page_count(self):
        fetch = fake_haystacks_api({1: ["A", "B"], 2: ["C", "D"], 3: ["E"]}, limit=2)

        with patch.object(device_service, "fetch_devices_metadata_from_space_invader_api", fetch):
            pages = [[d.name for d in devices] for devices in device_service._iter_device_pages(limit=2)]

        self.assertEqual(pages, [["A", "B"], ["C", "D"], ["E"]])
        self.assertEqual([c.kwargs["page"] for c in fetch.call_args_list], [1, 2, 3])

    def test_only_page_fetches_that_page(self):
        fetch = fake_haystacks_api({1: ["A", "B"], 2: ["C", "D"], 3: ["E"]}, limit=2)

        with patch.object(device_service, "fetch_devices_metadata_from_space_invader_api", fetch):
            pages = [[d.name for d in devices] for devices in device_service._iter_device_pages(limit=2, only_page=2)]

        self.assertEqual(pages, [["C", "D"]])
        self.assertEqual([c.kwargs["page"] for c in fetch.call_args_list], [2])

    def test_stops_on_empty_page(self):
        fetch = MagicMock(side_effect=[
            make_page(1, ["A", "B"], total=6, limit=2),
            make_page(2, [], total=6, limit=2),
        ])

        with patch.object(device_service, "fetch_devices_metadata_from_space_invader_api", fetch):
            pages = list(device_service._iter_device_pages(limit=2))

        self.assertEqual(len(pages), 1)
        self.assertEqual(fetch.call_count, 2)

    def test_no_active_devices(self):
        fetch = fake_haystacks_api({}, limit=2)

        with patch.object(device_service, "fetch_devices_metadata_from_space_invader_api", fetch):
            self.assertEqual(list(device_service._iter_device_pages(limit=2)), [])


class FetchAndReportLocationsTest(unittest.TestCase):
    def setUp(self):
        self.fetch = fake_haystacks_api({1: ["A", "B"], 2: ["C", "D"], 3: ["E"]}, limit=2)
        self.apple_fetch = MagicMock(return_value=ResponseDto(results=[], statusCode="200"))
        self.send = MagicMock()
        patches = [
            patch.object(device_service, "fetch_devices_metadata_from_space_invader_api", self.fetch),
            patch.object(device_service, "apple_fetch", self.apple_fetch),
            patch.object(device_service, "create_reports", side_effect=self.report_every_device),
            patch.object(device_service, "_send_device_locations_to_space_invader_api", self.send),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    @staticmethod
    def report_every_device(locations, devices):
        for device in devices:
            device.report = {
                "lat": 1, "lon": 2, "conf": 0.5, "status": 0,
                "device_id": device.name, "timestamp": 0, "description": "",
            }
        return {device.public_hash_base64 + device.name: device for device in devices}

    def test_reports_devices_from_every_page(self):
        reported = device_service.fetch_and_report_locations_for_devices(
            credentials_service=MagicMock(), limit=2, minutes_ago=15,
        )

        self.assertEqual([d.name for d in reported], ["A", "B", "C", "D", "E"])
        self.assertEqual(self.apple_fetch.call_count, 3)
        sent = [[d.name for d in c.args[0]] for c in self.send.call_args_list]
        self.assertEqual(sent, [["A", "B"], ["C", "D"], ["E"]])

    def test_trackers_filter_skips_pages_without_matches(self):
        reported = device_service.fetch_and_report_locations_for_devices(
            credentials_service=MagicMock(), limit=2, minutes_ago=15, trackers_filter={"D"}, send_reports=False,
        )

        self.assertEqual([d.name for d in reported], ["D"])
        self.assertEqual(self.apple_fetch.call_count, 1)
        self.send.assert_not_called()


class ScheduleTest(unittest.TestCase):
    def test_sends_one_message_without_page(self):
        with patch.object(sqs, "sqs") as client:
            client.send_message.return_value = {"MessageId": "m-1"}
            sqs.schedule_device_location_metadata_enrichment("https://queue.test", batch_size=2500)

        client.send_message.assert_called_once()
        self.assertEqual(json.loads(client.send_message.call_args.kwargs["MessageBody"]), {
            "limit": 2500,
            "minutes_ago": 15,
        })


class FetchLocationsHandlerTest(unittest.TestCase):
    def test_processes_all_pages_for_old_and_new_messages(self):
        import entrypoint

        for body in ({"limit": 2500, "minutes_ago": 15}, {"page": 0, "limit": 2500, "minutes_ago": 15}):
            with self.subTest(body=body), patch.object(entrypoint, "fetch_and_report_locations_for_devices") as run:
                result = entrypoint.fetch_locations_and_report({"Records": [{"body": json.dumps(body)}]}, None)

                self.assertEqual(result["statusCode"], 200)
                self.assertNotIn("page", run.call_args.kwargs)
                self.assertEqual(run.call_args.kwargs["limit"], 2500)


if __name__ == "__main__":
    unittest.main()
