import logging
import struct
from base64 import b64decode
from app.apple_fetch import AppleLocation
from app.cryptic import bytes_to_int, get_result
from app.dtos import BeamerDevice, EnrichedReport, Report
from app.date import EPOCH_DIFF

logger = logging.getLogger(__name__)


def decode_tag(data):
    latitude = struct.unpack(">i", data[0:4])[0] / 10000000.0
    longitude = struct.unpack(">i", data[4:8])[0] / 10000000.0
    confidence = bytes_to_int(data[8:9])
    status = bytes_to_int(data[9:10])
    return {"lat": latitude, "lon": longitude, "conf": confidence, "status": status}


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
            # logger.exception(f"Failed to decode tag for device {device.name}", extra={
            #     "device": device,
            #     "error": str(e),
            #     "icloud_payload": data,
            # })
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
