import logging
from base64 import b64decode

from pydantic import BaseModel, Field

from app.apple_fetch import AppleLocation
from app.cryptic import bytes_to_int, get_result
from app.dtos import BeamerDevice, EnrichedReport, Report
from app.haystack import decode_tag
from app.date import EPOCH_DIFF

logger = logging.getLogger(__name__)


def create_reports(locations: list[AppleLocation], devices: list[BeamerDevice]):
    """Decrypt payload and create a report"""
    device_mapping = {device.public_hash_base64: device for device in devices}
    for location in locations:
        data = b64decode(location.payload)
        timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF

        device: BeamerDevice = device_mapping.get(location.id)
        if not device:
            logger.warning("Device not found for location", extra={"location": location})
            continue
        try:
            report = decode_tag(get_result(device.private_key_numeric, data))
            report = Report(**report)
        except ValueError as e:
            # TODO: investigate these cases
            # logger.exception(f"Failed to decode tag for device {device.id} ({data}) with error: {e}")
            continue

        enriched_report = EnrichedReport(
            **report.model_dump(),
            device_id=device.id,
            timestamp=timestamp,
            date_published=location.date_published,
            description=location.description,
        )
        device.report = enriched_report

    return device_mapping


# def create_reports(response_json, devices):
#     """Decrypt payload and create a report"""
#     results = []
#     for result in response_json["results"]:
#         data = b64decode(result["payload"])
#         timestamp = bytes_to_int(data[0:4]) + EPOCH_DIFF
#         device = devices[result["id"]]
#         private_key = device["privateKeyNumeric"]
#         report = decode_tag(get_result(private_key, data))
#         report["timestamp"] = timestamp
#         report["datePublished"] = result["datePublished"]
#         report["description"] = result["description"]
#         device["report"] = report
#         results.append(device)
#     return results
