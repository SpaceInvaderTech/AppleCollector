"""
Decrypt payload and create a report
"""

from base64 import b64decode
from cryptic import bytes_to_int, get_result
from haystack import decode_tag
from date import EPOCH_DIFF


def create_reports(response_json, devices):
    """Decrypt payload and create a report"""
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
    return results
