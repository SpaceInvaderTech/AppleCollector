#!/usr/bin/env python3

"""
- Fetch private keys from API.
- Send reports to API.
"""

from argparse import ArgumentParser
import json
from api import fetch_devices, send_reports
from cryptic import b64_ascii, get_hashed_public_key, bytes_to_int
from apple_fetch import apple_fetch
from report import create_reports


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
    command_args = get_args()

    beamer_devices = fetch_devices(
        command_args.startpoint, headers=command_args.headers
    )
    if command_args.verbose:
        print("Beamers:", len(beamer_devices))

    device_mapping = {}
    for device in beamer_devices:
        privateKeyBytes = bytes(device["privateKey"]["data"])
        del device["privateKey"]
        device["privateKeyNumeric"] = bytes_to_int(privateKeyBytes)
        publicHashBase64 = b64_ascii(get_hashed_public_key(privateKeyBytes))
        device_mapping[publicHashBase64] = device

    apple_result = apple_fetch(command_args.key, list(device_mapping.keys()))
    if command_args.verbose:
        print("Results:", len(apple_result["results"]))

    report_list = create_reports(apple_result, device_mapping)
    for report in report_list:
        if "privateKeyNumeric" in report:
            del report["privateKeyNumeric"]

    send_reports(command_args.endpoint, report_list, headers=command_args.headers)
    if command_args.verbose:
        print(report_list)
