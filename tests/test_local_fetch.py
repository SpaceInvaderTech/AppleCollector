import json
import logging
import os
import struct
import sys
import tempfile
import types
import unittest
from base64 import b64encode
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.apple_fetch import AppleLocation, ResponseDto
from app.cryptic import sha256
from app.credentials.api import api_credentials_service
from app.date import EPOCH_DIFF
from app.dtos import BeamerDevice, LocalFetchResult
from app.key_cache import KeyCache, MacKeychain
from app.report import create_reports, decrypt_all_reports
from commands import location_and_reports


def make_device(name: str, key_byte: int = 1) -> BeamerDevice:
    return BeamerDevice(id=f"id-{name}", name=name, privateKey={"type": "Buffer", "data": [key_byte] * 28})


def encrypt_location(device: BeamerDevice, timestamp: int, lat: float, lon: float, conf: int = 50) -> AppleLocation:
    """The inverse of app.cryptic.get_result, so tests can build payloads Apple would return."""
    device_public = ec.derive_private_key(device.private_key_numeric, ec.SECP224R1()).public_key()
    ephemeral = ec.generate_private_key(ec.SECP224R1())
    ephemeral_bytes = ephemeral.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    symmetric_key = sha256(ephemeral.exchange(ec.ECDH(), device_public) + b"\x00\x00\x00\x01" + ephemeral_bytes)
    plaintext = struct.pack(">ii", int(lat * 1e7), int(lon * 1e7)) + bytes([conf, 0])
    encrypted = AESGCM(symmetric_key[:16]).encrypt(symmetric_key[16:], plaintext, None)

    payload = struct.pack(">I", timestamp - EPOCH_DIFF) + b"\x00" + ephemeral_bytes + encrypted
    return AppleLocation(
        payload=b64encode(payload).decode(), description="found", id=device.public_hash_base64,
        statusCode=200, datePublished=timestamp + 60,
    )


class DecryptAllReportsTest(unittest.TestCase):
    def test_keeps_every_report_per_device_sorted(self):
        a, b = make_device("A", 1), make_device("B", 2)
        locations = [
            encrypt_location(a, 1_700_000_200, 52.1, 4.3),
            encrypt_location(a, 1_700_000_100, 52.0, 4.2),
            encrypt_location(b, 1_700_000_300, 40.4, -3.7),
        ]

        reports = decrypt_all_reports(locations, [a, b])

        self.assertEqual([r.timestamp for r in reports["id-A"]], [1_700_000_100, 1_700_000_200])
        self.assertAlmostEqual(reports["id-A"][0].lat, 52.0)
        self.assertAlmostEqual(reports["id-A"][0].lon, 4.2)
        self.assertEqual(reports["id-A"][0].date_published, 1_700_000_160)
        self.assertEqual(len(reports["id-B"]), 1)

    def test_skips_duplicates_and_unknown_devices(self):
        a = make_device("A", 1)
        location = encrypt_location(a, 1_700_000_100, 52.0, 4.2)
        unknown = encrypt_location(make_device("X", 3), 1_700_000_100, 1.0, 1.0)

        reports = decrypt_all_reports([location, location, unknown], [a])

        self.assertEqual(list(reports), ["id-A"])
        self.assertEqual(len(reports["id-A"]), 1)

    def test_create_reports_still_keeps_one_report(self):
        a = make_device("A", 1)
        locations = [encrypt_location(a, 1_700_000_100, 52.0, 4.2), encrypt_location(a, 1_700_000_200, 52.1, 4.3)]

        device_map = create_reports(locations, [a])

        self.assertEqual(device_map[a.public_hash_base64].report.timestamp, 1_700_000_200)


class FakeKeychain(MacKeychain):
    def __init__(self):
        self.key = Fernet.generate_key()
        self.calls = 0

    def get_or_create_fernet_key(self) -> bytes:
        self.calls += 1
        return self.key


class KeyCacheTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cache" / "keys.bin"
        self.now = 1_000_000.0
        self.download = MagicMock(return_value=[make_device("A", 1), make_device("B", 2)])
        self.keychain = FakeKeychain()

    def cache(self) -> KeyCache:
        return KeyCache(path=self.path, download=self.download, keychain=self.keychain, clock=lambda: self.now)

    def test_miss_downloads_and_writes_encrypted_file(self):
        devices = self.cache().get_devices({"A"})

        self.assertEqual([d.name for d in devices], ["A"])
        self.download.assert_called_once()
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        content = self.path.read_bytes()
        self.assertNotIn(b"id-A", content)
        self.assertNotIn(b"privateKey", content)
        self.assertFalse(self.path.with_name("keys.bin.tmp").exists())

    def test_hit_uses_cache(self):
        self.cache().get_devices({"A"})

        devices = self.cache().get_devices({"B"})

        self.assertEqual([d.name for d in devices], ["B"])
        self.assertEqual(devices[0].private_key_bytes, bytes([2] * 28))
        self.download.assert_called_once()

    def test_expired_cache_downloads_again(self):
        self.cache().get_devices({"A"})
        self.now += 24 * 60 * 60 + 1

        self.cache().get_devices({"A"})

        self.assertEqual(self.download.call_count, 2)

    def test_refresh_flag_downloads_again(self):
        self.cache().get_devices({"A"})

        self.cache().get_devices({"A"}, refresh=True)

        self.assertEqual(self.download.call_count, 2)

    def test_missing_tracker_refreshes_once_and_is_left_out(self):
        self.cache().get_devices({"A"})

        devices = self.cache().get_devices({"A", "NOPE"})

        self.assertEqual([d.name for d in devices], ["A"])
        self.assertEqual(self.download.call_count, 2)

    def test_no_trackers_returns_all_cached(self):
        self.cache().get_devices()

        self.assertEqual([d.name for d in self.cache().get_devices()], ["A", "B"])
        self.download.assert_called_once()

    def test_undecryptable_cache_downloads_again(self):
        self.cache().get_devices({"A"})
        self.keychain.key = Fernet.generate_key()

        self.cache().get_devices({"A"})

        self.assertEqual(self.download.call_count, 2)


class CollectAllReportsTest(unittest.TestCase):
    def test_json_shape(self):
        a, b = make_device("A", 1), make_device("B", 2)
        locations = [encrypt_location(a, 1_700_000_100, 52.0, 4.2), encrypt_location(a, 1_700_000_200, 52.1, 4.3)]
        credentials = MagicMock()
        apple_fetch = MagicMock(return_value=ResponseDto(results=locations, statusCode="200"))

        with patch.object(location_and_reports, "fetch_devices", return_value=[a, b, make_device("C", 3)]), \
                patch("app.device_service.apple_fetch", apple_fetch):
            result = json.loads(location_and_reports.collect_all_reports(
                credentials_service=credentials, tracker_ids={"A", "B", "MISSING"}, minutes_ago=60,
            ).model_dump_json())

        self.assertEqual(result["requested"], ["A", "B", "MISSING"])
        self.assertEqual(result["missing"], ["MISSING"])
        self.assertEqual([beam["name"] for beam in result["beams"]], ["A", "B"])
        self.assertEqual(result["beams"][0]["id"], "id-A")
        self.assertEqual(len(result["beams"][0]["reports"]), 2)
        self.assertEqual(result["beams"][1]["reports"], [])
        self.assertEqual(
            set(result["beams"][0]["reports"][0]),
            {"timestamp", "date_published", "lat", "lon", "conf", "status"},
        )
        self.assertIs(apple_fetch.call_args.kwargs["credentials_service"], credentials)

    def test_uses_key_cache_when_given(self):
        cache = MagicMock()
        cache.get_devices.return_value = []

        with patch.object(location_and_reports, "KeyCache", return_value=cache) as key_cache, \
                patch.object(location_and_reports, "fetch_devices") as fetch_devices:
            result = location_and_reports.collect_all_reports(
                credentials_service=MagicMock(), tracker_ids={"A"}, minutes_ago=60,
                key_cache_path="/tmp/keys.bin", refresh_keys=True,
            )

        self.assertEqual(key_cache.call_args.kwargs["path"], "/tmp/keys.bin")
        cache.get_devices.assert_called_once_with({"A"}, refresh=True)
        fetch_devices.assert_not_called()
        self.assertEqual(result, LocalFetchResult(beams=[], requested=["A"], missing=["A"]))


class KeychainCredentialsServiceTest(unittest.TestCase):
    def test_reads_keychain_on_every_call_and_never_stores(self):
        headers = {
            "User-Agent": "ua", "Accept": "application/json", "Authorization": "Basic x",
            "X-Apple-I-MD": "md", "X-Apple-I-MD-RINFO": "17106176", "X-Apple-I-MD-M": "m",
            "X-Apple-I-TimeZone": "CET", "X-Apple-I-Client-Time": "t", "X-BA-CLIENT-TIMESTAMP": "1",
        }
        fake_haystack = types.SimpleNamespace(get_headers=MagicMock(return_value=headers))

        with patch.dict(sys.modules, {"app.haystack": fake_haystack}):
            from app.credentials.keychain import KeychainCredentialsService
            service = KeychainCredentialsService()
            service.get_credentials()
            credentials = service.get_credentials()

        self.assertEqual(fake_haystack.get_headers.call_count, 2)
        self.assertEqual(credentials.authorization, "Basic x")
        with self.assertRaises(NotImplementedError):
            service.update_credentials(credentials)


class FetchLocationsCliTest(unittest.TestCase):
    def setUp(self):
        import manage
        self.manage = manage
        root = logging.getLogger()
        streams = [(h, h.stream) for h in root.handlers if isinstance(h, logging.StreamHandler)]
        self.addCleanup(lambda: [h.setStream(s) for h, s in streams])

    def invoke(self, *args):
        return CliRunner(mix_stderr=False).invoke(self.manage.cli, ["fetch-locations", *args])

    def test_default_path_uses_api_credentials_service(self):
        with patch.object(self.manage, "resolve_locations") as resolve:
            result = self.invoke("-t", "A,B", "--minutes-ago", "15")

        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIs(resolve.call_args.kwargs["credentials_service"], api_credentials_service)
        self.assertEqual(resolve.call_args.kwargs["tracker_ids"], {"A", "B"})

    def test_local_credentials_uses_keychain(self):
        from app.credentials.keychain import KeychainCredentialsService

        with patch.object(self.manage, "resolve_locations") as resolve:
            result = self.invoke("-t", "A", "--local-credentials")

        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertIsInstance(resolve.call_args.kwargs["credentials_service"], KeychainCredentialsService)

    def test_json_output_is_only_json_on_stdout(self):
        payload = LocalFetchResult(beams=[], requested=["A"], missing=["A"])

        def collect(**kwargs):
            logging.getLogger("test").info("a log line")
            return payload

        with patch.object(self.manage, "collect_all_reports", side_effect=collect) as run:
            result = self.invoke("-t", "A", "--output", "json", "--key-cache", "/tmp/k.bin", "--refresh-keys")

        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), payload.model_dump())
        self.assertIn("a log line", result.stderr)
        self.assertEqual(run.call_args.kwargs["key_cache_path"], "/tmp/k.bin")
        self.assertTrue(run.call_args.kwargs["refresh_keys"])

    def test_minutes_ago_capped_at_seven_days(self):
        with patch.object(self.manage, "resolve_locations") as resolve:
            ok = self.invoke("-t", "A", "--minutes-ago", "10080")
            too_far = self.invoke("-t", "A", "--minutes-ago", "10081")

        self.assertEqual(ok.exit_code, 0, ok.stderr)
        self.assertEqual(too_far.exit_code, 2)
        self.assertIn("at most 10080 (7 days)", too_far.stderr)
        resolve.assert_called_once()

    def test_send_reports_rejected_with_local_output(self):
        result = self.invoke("-t", "A", "--output", "json", "--send-reports")

        self.assertEqual(result.exit_code, 2)

    def test_since_until_become_a_utc_time_range(self):
        payload = LocalFetchResult(beams=[], requested=["A"], missing=[])
        with patch.object(self.manage, "collect_all_reports", return_value=payload) as run:
            result = self.invoke("-t", "A", "--output", "json", "--since", "2026-11-10T08:00:00", "--until", "2026-11-10T08:15:00+00:00")

        self.assertEqual(result.exit_code, 0, result.stderr)
        self.assertEqual(run.call_args.kwargs["time_range"], (1794297600, 1794298500))

    def test_without_since_until_there_is_no_time_range(self):
        payload = LocalFetchResult(beams=[], requested=["A"], missing=[])
        with patch.object(self.manage, "collect_all_reports", return_value=payload) as run:
            self.invoke("-t", "A", "--output", "json")

        self.assertIsNone(run.call_args.kwargs["time_range"])

    def test_bad_time_ranges_are_rejected(self):
        for args in (
            ["--since", "2026-11-10T08:00:00"],
            ["--since", "2026-11-10T09:00:00", "--until", "2026-11-10T08:00:00"],
            ["--since", "2026-10-01T00:00:00", "--until", "2026-11-10T00:00:00"],
            ["--since", "yesterday", "--until", "2026-11-10T00:00:00"],
        ):
            with self.subTest(args=args):
                self.assertEqual(self.invoke("-t", "A", "--output", "json", *args).exit_code, 2)

    def test_time_range_needs_the_local_output(self):
        with patch.object(self.manage, "resolve_locations") as resolve:
            result = self.invoke("-t", "A", "--since", "2026-11-10T08:00:00", "--until", "2026-11-10T08:15:00")

        self.assertEqual(result.exit_code, 2)
        resolve.assert_not_called()


class AppleFetchTimeRangeTest(unittest.TestCase):
    def test_time_range_overrides_minutes_ago(self):
        from app import apple_fetch as module

        with patch.object(module, "generate_request_payloads", return_value=[]) as generate, \
                patch.object(module, "merge_successful_responses"):
            module.apple_fetch(MagicMock(), ["id"], minutes_ago=15, time_range=(1_000_000, 1_000_000 + 7200))

        self.assertEqual(generate.call_args.kwargs["start_date"], 1_000_000)
        self.assertEqual(generate.call_args.kwargs["end_date"], 1_000_000 + 7200)
        self.assertEqual(generate.call_args.kwargs["time_chunk_size"], 3600 * 24)


if __name__ == "__main__":
    unittest.main()
