"""
Fetch from Apple's acsnservice
"""
import datetime
import logging
import time
from collections import deque

from requests import Session
from app.credentials.base import CredentialsService
from app.exceptions import AppleAuthCredentialsExpired
from app.helpers import status_code_success
from app.date import unix_epoch, date_milliseconds
from pydantic import BaseModel, Field

from app.settings import settings
from typing import TypedDict


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


def apple_fetch(credentials_service: CredentialsService, ids: list[str], minutes_ago: int = 15) -> ResponseDto:
    logger.info("Fetching locations from Apple API for %s IDs with %d minutes lookback", len(ids), minutes_ago)
    start_date = unix_epoch() - minutes_ago * 60
    end_date = unix_epoch()

    if is_short_time_range(start_date, end_date):
        logger.info("Using ID-only batching strategy (time range < 20 minutes)")
        payloads = generate_request_payloads(
            device_ids=ids, start_date=start_date, end_date=end_date, device_batch_size=10, time_chunk_size=None
        )
    else:
        logger.info("Using ID+time batching strategy (time range >= 20 minutes)")
        # 3600 (seconds in an hour) * 24(hours in a day) = seconds in a day
        payloads = generate_request_payloads(
            device_ids=ids, start_date=start_date, end_date=end_date, device_batch_size=10, time_chunk_size=3600*24
        )

    responses = try_fetch_payloads(credentials_service, payloads, max_attempts_per_payload=2)

    return merge_successful_responses(responses)


def is_short_time_range(start_date: int, end_date: int) -> bool:
    twenty_minutes_in_seconds = 20 * 60
    return (end_date - start_date) < twenty_minutes_in_seconds


def build_acsnservice_payload(ids: list[str], start_date: int, end_date: int) -> dict:
    return {
        "startDate": date_milliseconds(start_date),
        "endDate": date_milliseconds(end_date),
        "ids": ids,
    }


def create_id_batches(ids: list, batch_size: int) -> list[list]:
    return [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]


def create_time_chunks(start_date: int, end_date: int, time_chunk_size_in_seconds: int) -> list[tuple[int, int]]:
    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + time_chunk_size_in_seconds, end_date)
        chunks.append((current_start, current_end))
        current_start = current_end

    return chunks


def generate_request_payloads(device_ids: list[str], start_date: int, end_date: int, device_batch_size: int = 20, time_chunk_size: int = None):
    payloads = []
    id_batches = create_id_batches(device_ids, batch_size=device_batch_size)
    logger.info(f"Broke down {len(device_ids)} devices into {len(id_batches)} batches of {device_batch_size} devices each")

    time_chunks = [(start_date, end_date)]

    if time_chunk_size is not None:
        time_chunks = create_time_chunks(start_date, end_date, time_chunk_size)
        logger.info(f"Broke down time range into {len(time_chunks)} chunks of {time_chunk_size} seconds each")

    payloads = []
    for device_id_batch in id_batches:
        payloads.extend(
            [
                build_acsnservice_payload(device_id_batch, time_chunk[0], time_chunk[1])
                for time_chunk in time_chunks
            ]
        )

    logger.info(f"Created {len(payloads)} payloads")
    return payloads


def try_fetch_payloads(
        credentials_service: CredentialsService, payloads: list[dict], max_attempts_per_payload: int = 3,
        max_credentials_attempts: int = 10, wait_time_for_credentials_attempt: int = 1
) -> list:
    responses = []

    queue = deque(payloads)
    attempts = {}

    failed_payloads = 0
    successful_payloads = 0
    credentials_attempts = 0

    idx = 0

    security_headers = credentials_service\
        .get_credentials()\
        .model_dump(mode='json', by_alias=True)

    i = 0
    while len(queue) != 0:
        logger.info(f"Processing payload {i+1}/{len(payloads)}")

        payload = queue.popleft()
        key = " ".join(payload["ids"]) + str(payload["startDate"]) + str(payload["endDate"])

        try:
            response = _acsnservice_fetch(security_headers, payload["ids"], payload["startDate"], payload["endDate"])
        except Exception as e:
            logger.warning(f"Caught exception during Apple request: {e}")
            security_headers = credentials_service.get_credentials()
            if attempts.get(key, 0) <= max_attempts_per_payload:
                attempts[key] = attempts.get(key, 0) + 1
                queue.appendleft(payload)
                i -= 1

            continue

        if not status_code_success(response.status_code):
            logger.warning(f"Received {response.status_code} (Full response: `{response.text}`)")

            if response.status_code == 401:
                logger.info(
                    f"Got 401 - waiting for {wait_time_for_credentials_attempt} seconds and fetching credentials again"
                )
                time.sleep(wait_time_for_credentials_attempt)

                if credentials_attempts == max_credentials_attempts:
                    logger.error(
                        f"Credential fetching retries exceeded (max retries: {max_credentials_attempts}) - exiting early"
                    )
                    break

                credentials_attempts += 1

                security_headers = credentials_service \
                    .get_credentials() \
                    .model_dump(mode='json', by_alias=True)

            if attempts.get(key, 0) <= max_attempts_per_payload:
                attempts[key] = attempts.get(key, 0) + 1
                queue.appendleft(payload)
                i -= 1
        else:
            responses.append(response)

        i += 1

    logger.info(f"Completed fetching {len(payloads)} payloads")
    logger.info(f"{len(responses)}/{len(payloads)} responses retrieved")

    return responses


def merge_successful_responses(responses: list) -> ResponseDto:
    if not responses:
        logger.warning("No responses to merge")
        return create_empty_response_dto()

    if len(responses) == 1:
        response_dto = ResponseDto(**responses[0].json())
        logger.info("Single response with %d results", len(response_dto.results))
        return response_dto

    all_results = extract_and_combine_all_results(responses)
    logger.info("Merged %d responses into %d total results", len(responses), len(all_results))
    return create_merged_response_dto(all_results)


def extract_and_combine_all_results(responses: list) -> list[AppleLocation]:
    combined_results = []
    for response in responses:
        if status_code_success(response.status_code):
            response_data = response.json()
            response_dto = ResponseDto(**response_data)
            combined_results.extend(response_dto.results)
    return combined_results


def create_empty_response_dto() -> ResponseDto:
    return ResponseDto(results=[], statusCode="200")


def create_merged_response_dto(results: list[AppleLocation]) -> ResponseDto:
    return ResponseDto(results=results, statusCode="200")


def _acsnservice_fetch(security_headers, ids, startdate, enddate):
    return requestSession.post(
        "https://gateway.icloud.com/acsnservice/fetch",
        headers=security_headers,
        json={
            "search": [
                {
                    "startDate": date_milliseconds(startdate),
                    "endDate": date_milliseconds(enddate),
                    "ids": ids,
                }
            ]
        },
        timeout=60,
    )
