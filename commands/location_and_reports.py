import logging

from app.credentials.api import api_credentials_service
from app.dtos import BeamerDevice
from app.helpers import retry_on_apple_auth_expired
from app.models import ICloudCredentials
from app.settings import settings
from app.device_service import fetch_and_report_locations_for_devices
from app.credentials.api import api_credentials_service

logger = logging.getLogger(__name__)


def resolve_locations(
        tracker_ids: set[str] = None,
        limit: int = 3000,
        page: int = 0,
        send_reports: bool = True,
        minutes_ago: int = 15,
        print_report: bool = False,
) -> None:
    devices: list[BeamerDevice] = fetch_and_report_locations_for_devices(
        credentials_service=api_credentials_service,
        page=page,
        limit=limit,
        minutes_ago=minutes_ago,
        trackers_filter=tracker_ids,
        send_reports=send_reports,
    )

    if print_report:
        for device in devices:
            logger.info('*****************************************')
            logger.info(f'Fetched locations for device: {device.name} ({device.id})')
            logger.info(f'Report: {device.report}')
            logger.info('*****************************************')
