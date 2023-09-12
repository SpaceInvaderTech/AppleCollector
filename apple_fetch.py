"""
Fetch from Apple's acsnservice and send data to args.endpoint
"""

import sys
from os import path
from uuid import uuid3, NAMESPACE_DNS
from requests import post
from helpers import (
    bytes_to_int,
    acsnservice_fetch,
    status_code_success,
    b64decode,
    getResult,
)
from date import EPOCH_DIFF, unix_epoch

UUID_NAMESPACE = uuid3(NAMESPACE_DNS, "apple.com")
STATUS_CODE_FILE = "status_code.txt"


def apple_fetch(args, decryption_key, devices):
    """Fetch from Apple's acsnservice and send data to args.endpoint"""
    if path.isfile(STATUS_CODE_FILE):
        with open(STATUS_CODE_FILE, mode="r", encoding="utf-8") as status_code_stream:
            status_code_last = status_code_stream.read()
            if not status_code_success(int(status_code_last)):
                print(status_code_last)
                sys.exit()

    seconds_ago = 60 * args.minutes if args.minutes else 60 * 60 * args.hours
    startdate = unix_epoch() - seconds_ago
    enddate = unix_epoch()

    response = acsnservice_fetch(
        decryption_key, list(devices.keys()), startdate, enddate
    )

    with open(STATUS_CODE_FILE, mode="w", encoding="utf-8") as status_code_stream:
        status_code_stream.write(str(response.status_code))

    if args.verbose or not status_code_success(response.status_code):
        print("acsnservice_fetch", response.status_code, response.reason)

    response_json = response.json()

    if args.verbose:
        print("num results", len(response_json["results"]))

    results = {}
    for result in response_json["results"]:
        data = b64decode(result["payload"])
        timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF
        private_key = bytes_to_int(devices[result["id"]]["privateKey"])
        report = getResult(private_key, data)
        report["name"] = devices[result["id"]]["name"]
        report["timestamp"] = timestamp
        report["datePublished"] = result["datePublished"]
        report["description"] = result["description"]
        signal_uuid = uuid3(UUID_NAMESPACE, "-".join([report["name"], str(timestamp)]))
        results[str(signal_uuid)] = report

    if args.endpoint:
        response = post(
            args.endpoint,
            json=results,
            timeout=60,
        )
        if args.verbose or not status_code_success(response.status_code):
            print(
                args.endpoint,
                response.status_code,
                response.reason,
            )
