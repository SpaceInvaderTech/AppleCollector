"""
Fetch from Apple's acsnservice
"""

import sys
from os import path
from requests import post
from helpers import (
    bytes_to_int,
    acsnservice_fetch,
    status_code_success,
    b64decode,
    getResult,
)
from date import EPOCH_DIFF, unix_epoch


def apple_fetch(args, decryption_key, devices):
    if path.isfile("status_code.txt"):
        with open("status_code.txt", "r") as statusCodeFile:
            statusCodeLast = statusCodeFile.read()
            if not status_code_success(int(statusCodeLast)):
                print(statusCodeLast)
                sys.exit()

    seconds_ago = 60 * args.minutes if args.minutes else 60 * 60 * args.hours
    startdate = unix_epoch() - seconds_ago
    enddate = unix_epoch()

    response = acsnservice_fetch(
        decryption_key, list(devices.keys()), startdate, enddate
    )

    with open("status_code.txt", "w") as statusCodeFile:
        statusCodeFile.write(str(response.status_code))

    if args.verbose or not status_code_success(response.status_code):
        print("acsnservice_fetch", response.status_code, response.reason)

    response_json = response.json()
    if args.verbose:
        print("num results", len(response_json["results"]))
    for result in response_json["results"]:
        data = b64decode(result["payload"])
        timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF
        if timestamp >= startdate:
            private_key = bytes_to_int(devices[result["id"]]["privateKey"])
            report = getResult(private_key, data)
            report["name"] = devices[result["id"]]["name"]
            report["timestamp"] = timestamp
            if args.verbose or not args.endpoint:
                print(report)
            if args.endpoint:
                response = post(
                    args.endpoint,
                    json=report,
                    timeout=60,
                )
                if args.verbose or not status_code_success(response.status_code):
                    print(
                        args.endpoint,
                        response.status_code,
                        response.reason,
                    )
