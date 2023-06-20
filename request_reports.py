#!/usr/bin/env python3

"""
Request reports
"""

from argparse import ArgumentParser
from glob import glob
from base64 import b64decode
from datetime import datetime
from pathlib import Path
from helpers import (
    EPOCH_DIFF,
    bytes_to_int,
    retrieveICloudKey,
    unix_epoch,
    acsnservice_fetch,
    getResult,
)


def get_args():
    """Function returning script arguments"""
    parser = ArgumentParser()
    parser.add_argument(
        "-H",
        "--hours",
        help="only show reports not older than these hours",
        type=int,
        default=24,
    )
    parser.add_argument(
        "-M",
        "--minutes",
        help="only show reports not older than these minutes",
        type=int,
    )
    parser.add_argument(
        "-p", "--prefix", help="only use keyfiles starting with this prefix", default=""
    )
    parser.add_argument(
        "-k",
        "--key",
        help="iCloud decryption key ($ security find-generic-password -ws 'iCloud')",
    )
    return parser.parse_args()


def read_key_files(prefix):
    device_ids = {}
    file_names = {}
    for keyfile_path in glob(prefix + "*.keys"):
        name = Path(keyfile_path).stem
        with open(keyfile_path) as keyfile:
            hashed_adv = ""
            private_key = ""
            for line in keyfile:
                key = line.rstrip("\n").split(": ")
                if key[0] == "Private key":
                    private_key = key[1]
                elif key[0] == "Hashed adv key":
                    hashed_adv = key[1]
            if private_key and hashed_adv:
                device_ids[hashed_adv] = private_key
                file_names[hashed_adv] = name
            else:
                print("Couldn't find key pair in", keyfile)
    return device_ids, file_names


if __name__ == "__main__":
    args = get_args()

    iCloud_decryptionkey = args.key if args.key else retrieveICloudKey()
    ids, names = read_key_files(args.prefix)
    secondsAgo = 60 * args.minutes if args.minutes else 60 * 60 * args.hours
    startdate = unix_epoch() - secondsAgo

    response = acsnservice_fetch(iCloud_decryptionkey, list(ids.keys()), startdate)
    print(response.status_code, response.reason)
    results = response.json()["results"]
    print("%d reports received." % len(results))

    ordered = []
    found = set()
    for report in results:
        priv = bytes_to_int(b64decode(ids[report["id"]]))
        data = b64decode(report["payload"])
        timestamp = bytes_to_int(data[0:4])
        if timestamp + EPOCH_DIFF >= startdate:
            res = getResult(priv, data)
            res["timestamp"] = timestamp + EPOCH_DIFF
            res["isodatetime"] = datetime.fromtimestamp(res["timestamp"]).isoformat()
            res["key"] = names[report["id"]]
            res["goog"] = (
                "https://maps.google.com/maps?q="
                + str(res["lat"])
                + ","
                + str(res["lon"])
            )
            found.add(res["key"])
            ordered.append(res)

    print("%d reports used." % len(ordered))
    ordered.sort(key=lambda item: item.get("timestamp"))
    for rep in ordered:
        print(rep)
    print("found:   ", list(found))
    print("missing: ", [key for key in names.values() if key not in found])
