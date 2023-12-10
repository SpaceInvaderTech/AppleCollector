"""
Fetch from Apple's acsnservice
"""

from requests import Session
from haystack import get_headers
from helpers import status_code_success
from date import unix_epoch, date_milliseconds

requestSession = Session()


def acsnservice_fetch(decryption_key, ids, startdate, enddate):
    """Fetch from Apple's acsnservice"""
    data = {
        "search": [
            {
                "startDate": date_milliseconds(startdate),
                "endDate": date_milliseconds(enddate),
                "ids": ids,
            }
        ]
    }
    return requestSession.post(
        "https://gateway.icloud.com/acsnservice/fetch",
        headers=get_headers(decryption_key),
        json=data,
        timeout=60,
    )


def apple_fetch(decryption_key, ids):
    """Prepare apple fetch"""
    seconds_ago = 60 * 60 * 1
    startdate = unix_epoch() - seconds_ago
    enddate = unix_epoch()

    response = acsnservice_fetch(decryption_key, ids, startdate, enddate)

    if not status_code_success(response.status_code):
        print("acsnservice_fetch", response.status_code, response.reason)
        return {
            "results": [],
        }

    return response.json()
