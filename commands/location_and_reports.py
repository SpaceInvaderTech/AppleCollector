import logging

from app.dtos import BeamerDevice
from app.helpers import retry_on_apple_auth_expired
from app.models import ICloudCredentials
from app.settings import settings
from app.device_service import fetch_and_report_locations_for_devices
from app.http_credentials import credentials_retriever

logger = logging.getLogger(__name__)


@retry_on_apple_auth_expired(
    credential_refresh_func=lambda: ICloudCredentials(
        **credentials_retriever.get_headers(
            api_key=settings.CREDENTIALS_API_KEY
        )),
    max_retries=settings.MAX_RETRIES_ON_APPLE_AUTH_EXPIRED,
)
def resolve_locations(
        tracker_ids: set[str] = None,
        limit: int = 3000,
        page: int = 0,
        send_reports: bool = True,
        hours_ago: int = 1,
        print_report: bool = False,
) -> None:
    security_headers = credentials_retriever.get_headers(api_key=settings.CREDENTIALS_API_KEY)
    logger.info("Security headers retrieved successfully.")

    devices: list[BeamerDevice] = fetch_and_report_locations_for_devices(
        security_headers=ICloudCredentials(**security_headers),
        page=page,
        limit=limit,
        hours_ago=hours_ago,
        trackers_filter=tracker_ids,
        send_reports=send_reports,
    )

    if print_report:
        for device in devices:
            logger.info('*****************************************')
            logger.info(f'Fetched locations for device: {device.name} ({device.id})')
            logger.info(f'Report: {device.report}')
            logger.info('*****************************************')
