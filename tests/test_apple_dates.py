import unittest
from unittest.mock import MagicMock, patch

from app import apple_fetch as module

START = 1_793_527_200


class AppleRequestDatesTest(unittest.TestCase):
    def test_dates_reach_apple_in_milliseconds_once(self):
        payload = module.build_acsnservice_payload(["id"], START, START + 900)
        body = module.acsnservice_request_body(payload["ids"], payload["startDate"], payload["endDate"])
        self.assertEqual(body, {"search": [{"startDate": START * 1000, "endDate": (START + 900) * 1000, "ids": ["id"]}]})

    def test_fetch_posts_the_payload_dates_unchanged(self):
        session = MagicMock()
        session.__aenter__.return_value = session
        response = MagicMock(status=200)

        async def text():
            return "{}"

        async def post(url, json):
            session.sent = json
            response.text = text
            return response

        session.post = post
        with patch.object(module.aiohttp, "ClientSession", return_value=session):
            import asyncio
            asyncio.run(module._async_acsnservice_fetch({}, ["id"], START * 1000, (START + 900) * 1000))
        self.assertEqual(session.sent["search"][0]["startDate"], START * 1000)


class OneRequestPerBeamTest(unittest.TestCase):
    def test_long_lookback_is_not_split_by_day(self):
        with patch.object(module, "unix_epoch", return_value=START + 7 * 86400), \
                patch.object(module, "try_fetch_payloads") as fetch, \
                patch.object(module, "merge_successful_responses"):
            async def done(*args, **kwargs):
                return []
            fetch.side_effect = done
            module.apple_fetch(MagicMock(), ["a", "b"], minutes_ago=7 * 24 * 60)
        payloads = fetch.call_args.args[1]
        self.assertEqual([p["ids"] for p in payloads], [["a"], ["b"]])


if __name__ == "__main__":
    unittest.main()
