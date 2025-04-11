#!/usr/bin/env python3

"""
Export from Property Lists files
"""

from os import walk, path
from plistlib import load
from requests import put
from cryptic import b64_ascii

PLIST_DIR = "/tmp/plists"
URL = ""
HEADERS = {"X-API-Key": "xyz"}

if __name__ == "__main__":
    devices = []
    for root, dirs, files in walk(PLIST_DIR):
        for file in files:
            if file.endswith(".plist"):
                plist_path = path.join(root, file)
                print("Reading", plist_path)
                with open(plist_path, "rb") as plist:
                    for device in load(plist):
                        devices.append(
                            {
                                "name": device["name"],
                                "privateKey": b64_ascii(device["privateKey"]),
                            }
                        )
    print(devices)
    if URL.startswith("http"):
        response = put(URL, headers=HEADERS, json=devices, timeout=60)
        print("status_code:", response.status_code)
