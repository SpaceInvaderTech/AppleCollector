import logging
from time import sleep
from app.api import fetch_devices_metadata_from_space_invader_api, send_reports_to_api
from app.apple_fetch import apple_fetch, ResponseDto
from app.credentials.base import CredentialsService
from app.dtos import BeamerDevice, HaystackSignalInput
from app.exceptions import NoMoreLocationsToFetch
from app.helpers import chunks
from app.models import ICloudCredentials
from app.report import create_reports
from app.settings import settings

logger = logging.getLogger(__name__)


def fetch_and_report_locations_for_devices(
        credentials_service: CredentialsService,
        page: int,
        limit: int,
        minutes_ago: int,
        trackers_filter: set[str] = None,
        send_reports: bool = True,
):
    try:
        device_response = _get_device_metadata_from_space_invader_api(limit, page)
    except NoMoreLocationsToFetch:
        return []

    if trackers_filter and len(trackers_filter) > 0:
        devices_to_consider = [device for device in device_response.data if device.name in trackers_filter]
    else:
        devices_to_consider = device_response.data
    apple_result = _fetch_location_metadata_from_icloud(
        credentials_service=credentials_service, devices_to_consider=devices_to_consider, minutes_ago=minutes_ago
    )
    device_map = create_reports(locations=apple_result.results, devices=devices_to_consider)

    devices_with_reports = list(device_map.values())
    logger.info(f"Enriched {len(devices_with_reports)} devices with reports")

    if send_reports:
        _send_device_locations_to_space_invader_api(devices_with_reports)

    return devices_with_reports


def _send_device_locations_to_space_invader_api(devices_with_reports):
    for chunk in chunks(devices_with_reports, 100):
        logger.info(f"Sending {len(chunk)} reports to Haystacks API")
        report_dtos = [HaystackSignalInput.get_haystack_signal_from_device(device) for device in chunk if device.report]
        try:
            send_reports_to_api(
                settings.post_haystacks_endpoint,
                [dto.model_dump(exclude_none=True, mode='json') for dto in report_dtos],
                headers=settings.headers
            )
            sleep(0.5)
        except Exception as e:
            logger.error(f"Failed to send reports: {e}")
            continue


def fetch_limited_locations_and_generate_reports_for_them(
        credentials_service: CredentialsService,
        limit: int,
        page: int,
        trackers_filter: set[str],
        minutes_ago: int = 15,
) -> list[BeamerDevice]:
    try:
        device_response = _get_device_metadata_from_space_invader_api(limit, page)
    except NoMoreLocationsToFetch:
        return []

    devices_to_consider = [device for device in device_response.data if device.name in trackers_filter]
    apple_result = _fetch_location_metadata_from_icloud(
        credentials_service=credentials_service, devices_to_consider=devices_to_consider, minutes_ago=minutes_ago
    )
    device_map = create_reports(locations=apple_result.results, devices=devices_to_consider)

    return list(device_map.values())


def _fetch_location_metadata_from_icloud(
    credentials_service: CredentialsService,
    devices_to_consider: list[BeamerDevice],
    minutes_ago: int,
) -> ResponseDto:
    apple_result = apple_fetch(
        credentials_service=credentials_service,
        ids=[device.public_hash_base64 for device in devices_to_consider],
        minutes_ago=minutes_ago)
    if not apple_result.is_success:
        logger.error(f"Apple API Error[{apple_result.statusCode}]: {apple_result.error}")
        exit(1)
    logger.info(f"Fetched {len(apple_result.results)} location metadata")

    return apple_result


def _get_device_metadata_from_space_invader_api(limit, page):
    """
    :raises NoMoreLocationsToFetch: if no devices are found for the given page
    """
    device_response = fetch_devices_metadata_from_space_invader_api(
        settings.get_haystacks_endpoint,
        headers=settings.headers,
        limit=limit,
        page=page,
    )
    if len(device_response.data) == 0:
        logger.info(f"No devices found for page {page}.")
        raise NoMoreLocationsToFetch()
    logger.info(
        f"Fetched device metadata for page: {device_response.meta.page},"
        f" limit: {device_response.meta.limit} out of {device_response.meta.total} devices.")
    return device_response
