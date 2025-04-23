import logging
from requests import Session
from app.dtos import DeviceResponse
from app.helpers import status_code_success

requestSession = Session()
logger = logging.getLogger(__name__)


def fetch_devices_metadata_from_space_invader_api(
        url,
        headers=None,
        limit: int = 3000,
        page: int = 0,
) -> DeviceResponse:
    response = requestSession.get(url, headers=headers, timeout=60, params={
        "limit": limit,
        "offset": page,
    })
    _handle_response(response)
    return DeviceResponse(**response.json())


def send_reports_to_api(url, data, headers=None):
    """Send reports to API"""
    if not url:
        return

    response = requestSession.post(
        url,
        headers=headers,
        json=data,
        timeout=60,
    )
    _handle_response(response)


def _handle_response(response):
    if not status_code_success(response.status_code):
        raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
