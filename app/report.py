import datetime
import logging
import struct
import warnings
from base64 import b64decode
from app.apple_fetch import AppleLocation
from app.cryptic import bytes_to_int, get_result
from app.dtos import BeamerDevice, EnrichedReport, Report
from app.date import EPOCH_DIFF

logger = logging.getLogger(__name__)


class StatsAggregator:
    def __init__(self):
        self._no_locations_per_device = {}
        self._min_timestamp_per_device = {}
        self._max_timestamp_per_device = {}

    def add_report(self, beam_name: str, timestamp: int):
        self._no_locations_per_device[beam_name] = self._no_locations_per_device.get(beam_name, 0) + 1
        self._min_timestamp_per_device[beam_name] = min(self._min_timestamp_per_device.get(beam_name, timestamp), timestamp)
        self._max_timestamp_per_device[beam_name] = max(self._max_timestamp_per_device.get(beam_name, 0), timestamp)

    def get_stats(self) -> list[dict]:
        records = []

        for beam in sorted(self._no_locations_per_device.keys()):
            d = {
                "beam_name": beam,
                "no_locations": self._no_locations_per_device[beam],
                "min_timestamp": datetime.datetime.fromtimestamp(self._min_timestamp_per_device[beam]),
                "max_timestamp": datetime.datetime.fromtimestamp(self._max_timestamp_per_device[beam])
            }
            records.append(d)

        return records


def decode_tag(data):
    latitude = struct.unpack(">i", data[0:4])[0] / 10000000.0
    longitude = struct.unpack(">i", data[4:8])[0] / 10000000.0
    confidence = bytes_to_int(data[8:9])
    status = bytes_to_int(data[9:10])
    return {"lat": latitude, "lon": longitude, "conf": confidence, "status": status}


def create_reports(locations: list[AppleLocation], devices: list[BeamerDevice]):
    """Decrypt payload and create a report"""
    device_mapping = {device.public_hash_base64: device for device in devices}
    locations_per_device = {device.id: 0 for device in devices}

    stats_aggregator = StatsAggregator()

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
            stats_aggregator.add_report(device.name, timestamp)
        except Exception as e:
            logger.exception(f"Failed to decode tag for device {device.name}", extra={
                "device": device,
                "error": str(e),
                "icloud_payload": data,
            })
            continue

        enriched_report = EnrichedReport(
            **report.model_dump(),
            device_id=device.id,
            timestamp=timestamp,
            date_published=location.date_published,
            description=location.description,
        )
        device.report = enriched_report

    devices_with_locations = set()
    for device_stats in stats_aggregator.get_stats():
        logger.info(device_stats)
        devices_with_locations.add(device_stats["beam_name"])

    devices_without_locations = {device.name for device in devices if device.name not in devices_with_locations}

    logger.info(f"Devices with locations: {','.join(devices_with_locations)}")
    logger.info(f"Devices without locations: {','.join(devices_without_locations)}")

    return device_mapping
