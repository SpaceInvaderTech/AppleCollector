#!/usr/bin/env python3

"""
Read from Property Lists files
Show or send reports to URL
"""

import sys
from argparse import ArgumentParser
from os import walk, path
from plistlib import load
from base64 import b64encode
from requests import post
from helpers import (
    EPOCH_DIFF,
    bytes_to_int,
    int_to_bytes,
    sha256,
    get_public_key,
    retrieveICloudKey,
    unix_epoch,
    acsnservice_fetch,
    b64decode,
    getResult,
)


def get_args():
    """Returns script arguments"""
    parser = ArgumentParser()
    parser.add_argument("-p", "--path", help="path to PList file")
    parser.add_argument(
        "-H",
        "--hours",
        help="only get reports not older than these hours",
        type=int,
        default=24,
    )
    parser.add_argument(
        "-M",
        "--minutes",
        help="only get reports not older than these minutes",
        type=int,
    )
    parser.add_argument(
        "-k",
        "--key",
        help="iCloud decryption key ($ security find-generic-password -ws 'iCloud')",
    )
    parser.add_argument(
        "-e",
        "--endpoint",
        help="URL to send report",
    )
    parser.add_argument("-V", "--verbose", help="be verbose", action="store_true")
    return parser.parse_args()


def get_public_from_private(private_key):
    return int_to_bytes(get_public_key(bytes_to_int(private_key)), 28)


def get_hashed_public_key(private_key):
    return sha256(get_public_from_private(private_key))


def b64_ascii(encodable):
    return b64encode(encodable).decode("ascii")


def status_code_success(status_code):
    return status_code >= 200 < 300


if __name__ == "__main__":
    args = get_args()

    if path.isfile("status_code.txt"):
        with open("status_code.txt", "r") as statusCodeFile:
            statusCodeLast = statusCodeFile.read()
            if not status_code_success(int(statusCodeLast)):
                print(statusCodeLast)
                sys.exit()

    iCloud_decryptionkey = args.key if args.key else retrieveICloudKey()

    for root, dirs, files in walk(args.path):
        for file in files:
            if file.endswith(".plist"):
                plist_path = path.join(root, file)
                if args.verbose:
                    print("Reading", plist_path)
                with open(plist_path, "rb") as plist:
                    plistData = load(plist)

                    devices = {}
                    for device in plistData:
                        public_hash_b64 = b64_ascii(
                            get_hashed_public_key(device["privateKey"])
                        )
                        devices[public_hash_b64] = device

                    secondsAgo = (
                        60 * args.minutes if args.minutes else 60 * 60 * args.hours
                    )
                    startdate = unix_epoch() - secondsAgo

                    response = acsnservice_fetch(
                        iCloud_decryptionkey, list(devices.keys()), startdate
                    )
                    if args.verbose or not status_code_success(response.status_code):
                        print(
                            "acsnservice_fetch", response.status_code, response.reason
                        )

                    with open("status_code.txt", "w") as statusCodeFile:
                        statusCodeFile.write(str(response.status_code))

                    if not status_code_success(response.status_code):
                        print(response.text)
                        sys.exit()

                    response_json = response.json()
                    for result in response_json["results"]:
                        data = b64decode(result["payload"])
                        timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF
                        if timestamp >= startdate:
                            privateKey = bytes_to_int(
                                devices[result["id"]]["privateKey"]
                            )
                            report = getResult(privateKey, data)
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
                                if args.verbose or not status_code_success(
                                    response.status_code
                                ):
                                    print(
                                        args.endpoint,
                                        response.status_code,
                                        response.reason,
                                    )
