#!/usr/bin/env python3

"""
Read from Property Lists files
Show or send reports to URL
"""

from argparse import ArgumentParser
from os import walk, path
from plistlib import load
from base64 import b64encode
from itertools import islice
from time import sleep
from apple_fetch import apple_fetch
from helpers import (
    bytes_to_int,
    int_to_bytes,
    sha256,
    get_public_key,
    retrieveICloudKey,
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
    parser.add_argument(
        "-s",
        "--sleep",
        help="Seconds to sleep between requests",
        type=int,
        default=1,
    )
    parser.add_argument("-V", "--verbose", help="be verbose", action="store_true")
    return parser.parse_args()


def get_public_from_private(private_key):
    return int_to_bytes(get_public_key(bytes_to_int(private_key)), 28)


def get_hashed_public_key(private_key):
    return sha256(get_public_from_private(private_key))


def b64_ascii(encodable):
    return b64encode(encodable).decode("ascii")


def chunks(data, step):
    data_iterable = iter(data)
    for _ in range(0, len(data), step):
        yield {k: data[k] for k in islice(data_iterable, step)}


if __name__ == "__main__":
    args = get_args()
    iCloud_decryptionkey = args.key if args.key else retrieveICloudKey()
    devices = {}

    for root, dirs, files in walk(args.path):
        for file in files:
            if file.endswith(".plist"):
                plist_path = path.join(root, file)
                if args.verbose:
                    print("Reading", plist_path)
                with open(plist_path, "rb") as plist:
                    plistData = load(plist)
                    for device in plistData:
                        public_hash_b64 = b64_ascii(
                            get_hashed_public_key(device["privateKey"])
                        )
                        devices[public_hash_b64] = device

    for devices_chunk in chunks(devices, 10):
        apple_fetch(args, iCloud_decryptionkey, devices_chunk)
        sleep(args.sleep)
