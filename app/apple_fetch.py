"""
Fetch from Apple's acsnservice
"""
import logging
from requests import Session

from app.exceptions import AppleAuthCredentialsExpired
from app.helpers import status_code_success
from app.date import unix_epoch, date_milliseconds
from pydantic import BaseModel, Field

requestSession = Session()
logger = logging.getLogger(__name__)


class AppleLocation(BaseModel):
    date_published: int = Field(alias="datePublished")
    payload: str
    description: str
    id: str
    status_code: int = Field(alias="statusCode")

    class Config:
        populate_by_name = True
        validate_by_name = True


class ResponseDto(BaseModel):
    results: list[AppleLocation] = Field(default_factory=list)
    statusCode: str
    error: str = Field(default=None)

    @property
    def is_success(self) -> bool:
        return self.statusCode == "200"


def apple_fetch(security_headers: dict, ids, hours_ago: int = 1) -> ResponseDto:
    logger.info("Fetching locations from Apple API for %s", ids)
    startdate = unix_epoch() - hours_ago * 60 * 60
    enddate = unix_epoch()

    response = _acsnservice_fetch(security_headers, ids, startdate, enddate)

    if not status_code_success(response.status_code):
        if response.status_code == 401:
            raise AppleAuthCredentialsExpired(response.reason)

        logger.error('Error from Apple API: %s %s', response.status_code, response.reason)
        return ResponseDto(error=response.reason, statusCode=str(response.status_code))

    return ResponseDto(**response.json())


def _acsnservice_fetch(security_headers, ids, startdate, enddate):
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
        headers=security_headers,
        json=data,
        timeout=60,
    )
