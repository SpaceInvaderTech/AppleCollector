#!/usr/bin/env python3

"""
- Fetch private keys from API.
- Send reports to API.
"""

from argparse import ArgumentParser
import json
from api import fetch_devices
from cryptic import b64_ascii, get_hashed_public_key, bytes_to_int
from apple_fetch import apple_fetch
from report import report_result


def get_args():
    """Returns script arguments"""
    parser = ArgumentParser()
    parser.add_argument(
        "-k",
        "--key",
        required=True,
        help="iCloud decryption key ($ security find-generic-password -ws 'iCloud')",
    )
    parser.add_argument(
        "-s",
        "--startpoint",
        help="URL to get devices from",
    )
    parser.add_argument(
        "-x",
        "--headers",
        type=json.loads,
        help="Headers for API",
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        help="URL to send report",
    )
    parser.add_argument("-V", "--verbose", help="be verbose", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    beamers = fetch_devices(args.startpoint, headers=args.headers)
    devices = {}
    for device in beamers:
        private_key_bytes = bytes(device["privateKey"]["data"])
        device["privateKeyInt"] = bytes_to_int(private_key_bytes)
        public_hash_b64 = b64_ascii(get_hashed_public_key(private_key_bytes))
        devices[public_hash_b64] = device
    result = apple_fetch(args.key, list(devices.keys()))
    if args.verbose:
        print("num results", len(result["results"]))
    report = report_result(
        result, devices, endpoint=args.endpoint, headers=args.headers
    )
    if args.verbose:
        print(report)
