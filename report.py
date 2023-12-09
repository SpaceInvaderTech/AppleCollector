"""
Decrypt payload and send data to endpoint
"""

from base64 import b64decode
from requests import post
from cryptic import bytes_to_int, get_result
from haystack import decode_tag
from date import EPOCH_DIFF
from helpers import status_code_success


def report_result(response_json, devices, endpoint=None, headers=None):
    """Decrypt payload and send data to endpoint"""
    results = []

    for result in response_json["results"]:
        data = b64decode(result["payload"])
        timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF
        device = devices[result["id"]]
        private_key = device["privateKeyInt"]
        report = decode_tag(get_result(private_key, data))
        report["timestamp"] = timestamp
        report["datePublished"] = result["datePublished"]
        report["description"] = result["description"]
        device["report"] = report
        results.append(device)

    if endpoint:
        response = post(
            endpoint,
            headers=headers,
            json=results,
            timeout=60,
        )

        if not status_code_success(response.status_code):
            print(
                endpoint,
                response.status_code,
                response.reason,
            )

    return results
