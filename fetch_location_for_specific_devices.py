from app.dtos import BeamerDevice
from app.helpers import retry_on_apple_auth_expired
from app.models import ICloudCredentials
from app.sentry import setup_sentry
from app.settings import settings
import json
from app.device_service import fetch_and_report_locations_for_devices, fetch_limited_locations
from app.http_credentials import credentials_retriever
import logging.config

setup_sentry()
logger = logging.getLogger(__name__)
with open('app/logging.json', 'rt') as f:
    config = json.load(f)
    logging.config.dictConfig(config)


@retry_on_apple_auth_expired(
    credential_refresh_func=lambda: ICloudCredentials(
        **credentials_retriever.get_headers(
            api_key=settings.CREDENTIALS_API_KEY
        ))
)
def get_device_reports(headers: ICloudCredentials, limit, page, trackers_filter=None):
    return fetch_limited_locations(
        security_headers=headers,
        limit=limit,
        page=page,
        trackers_filter=trackers_filter,
        hours_ago=24
    )


if __name__ == "__main__":
    security_headers = credentials_retriever.get_headers(api_key=settings.CREDENTIALS_API_KEY)
    logger.info("Security headers retrieved successfully.")

    devices: list[BeamerDevice] = get_device_reports(
        headers=ICloudCredentials(**security_headers),
        limit=1000,
        page=0,
        trackers_filter={
            'E0D4FA128FA9',
            'EC3987ECAA50',
            'CDAA0CCF4128',
            'EDDC7DA1A247',
            'D173D540749D'
        },
    )

    for device in devices:
        logger.info('*****************************************')
        logger.info(f'Fetched locations for device: {device.name} ({device.id})')
        logger.info(f'Report: {device.report}')
        logger.info('*****************************************')
