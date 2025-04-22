import logging
from time import sleep
from app.api import fetch_devices_metadata_from_space_invader_api, send_reports
from app.apple_fetch import apple_fetch
from app.dtos import HaystackSignalInput
from app.helpers import chunks
from app.models import ICloudCredentials
from app.report import create_reports
from app.settings import settings

logger = logging.getLogger(__name__)


def fetch_and_report_locations_for_devices(security_headers: ICloudCredentials, page: int):
    # Fetch devices from Space Invader API - can be done on AWS
    device_response = fetch_devices_metadata_from_space_invader_api(
        settings.get_haystacks_endpoint,
        headers=settings.headers,
        limit=settings.DEVICE_BATCH_SIZE,  # 2135 in total
        page=page,
    )
    if len(device_response.data) == 0:
        logger.info(f"No devices found for page {page}.")
        return
    logger.info(
        f"Fetched device metadata for page: {device_response.meta.page},"
        f" limit: {device_response.meta.limit} out of {device_response.meta.total} devices.")
    devices_chunk = device_response.data
    apple_result = apple_fetch(
        security_headers.model_dump(mode='json', by_alias=True),
        [device.public_hash_base64 for device in devices_chunk])
    if not apple_result.is_success:
        logger.error(f"Apple API Error[{apple_result.statusCode}]: {apple_result.error}")
        exit(1)
    logger.info(f"Fetched {len(apple_result.results)} location metadata")
    device_map = create_reports(locations=apple_result.results, devices=devices_chunk)
    devices_with_reports = list(device_map.values())
    logger.info(f"Enriched {len(devices_with_reports)} devices with reports")
    for chunk in chunks(devices_with_reports, 100):
        logger.info(f"Sending {len(chunk)} reports to Haystacks API")
        report_dtos = [HaystackSignalInput.get_haystack_signal_from_device(device) for device in chunk if device.report]
        try:
            send_reports(
                settings.post_haystacks_endpoint,
                [dto.model_dump(exclude_none=True, mode='json') for dto in report_dtos],
                headers=settings.headers
            )
        except Exception as e:
            logger.error(f"Failed to send reports: {e}")
            continue
    sleep(0.1)
