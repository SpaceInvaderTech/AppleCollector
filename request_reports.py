"""
Request reports
"""

#!/usr/bin/env python3

from argparse import ArgumentParser
from base64 import b64decode
from datetime import datetime
from requests import post
from helpers import (
    bytes_to_int,
    retrieveICloudKey,
    readKeyFiles,
    getHeaders,
    getResult,
)

EPOCH_DIFF = 978307200


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


if __name__ == "__main__":
    args = get_args()

    iCloud_decryptionkey = args.key if args.key else retrieveICloudKey()
    request_headers = getHeaders(iCloud_decryptionkey)
    ids, names = readKeyFiles(args.prefix)
    unixEpoch = int(datetime.now().strftime("%s"))
    secondsAgo = 60 * args.minutes if args.minutes else 60 * 60 * args.hours
    startdate = unixEpoch - secondsAgo

    data = {
        "search": [
            {
                "startDate": (startdate - EPOCH_DIFF) * 1000000,
                "endDate": (unixEpoch - EPOCH_DIFF) * 1000000,
                "ids": list(ids.keys()),
            }
        ]
    }

    # send out the whole thing
    response = post(
        "https://gateway.icloud.com/acsnservice/fetch",
        headers=request_headers,
        json=data,
        timeout=60,
    )
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
            res["isodatetime"] = datetime.datetime.fromtimestamp(
                res["timestamp"]
            ).isoformat()
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
