"""
API
"""

from requests import Session
from helpers import status_code_success

requestSession = Session()


def handle_response(response):
    """Handle response error"""
    if not status_code_success(response.status_code):
        print(response.status_code, response.reason)


def fetch_devices(url, headers=None):
    """Returns id and private key for devices"""
    response = requestSession.get(url, headers=headers, timeout=60)
    handle_response(response)
    return response.json()


def send_reports(url, data, headers=None):
    """Send reports to API"""
    if not url:
        return
    response = requestSession.post(
        url,
        headers=headers,
        json=data,
        timeout=60,
    )
    handle_response(response)
