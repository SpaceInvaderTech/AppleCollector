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


def apple_fetch(security_headers: dict, ids, minutes_ago: int = 15) -> ResponseDto:
    logger.info("Fetching locations from Apple API for %s IDs with %d minutes lookback", len(ids), minutes_ago)
    start_date = unix_epoch() - minutes_ago * 60
    end_date = unix_epoch()

    if is_short_time_range(start_date, end_date):
        logger.info("Using ID-only batching strategy (time range < 20 minutes)")
        responses = process_with_id_batching_only(security_headers, ids, start_date, end_date)
    else:
        logger.info("Using ID+time batching strategy (time range >= 20 minutes)")
        responses = process_with_id_and_time_batching(security_headers, ids, start_date, end_date)

    failed_response = find_first_failed_response(responses)
    if failed_response:
        if failed_response.status_code == 401:
            raise AppleAuthCredentialsExpired(failed_response.reason)

        logger.error('Error from Apple API: %s %s', failed_response.status_code, failed_response.reason)
        return ResponseDto(error=failed_response.reason, statusCode=str(failed_response.status_code))

    logger.info("Successfully completed all API requests, merging results")
    return merge_successful_responses(responses)


def is_short_time_range(start_date: int, end_date: int) -> bool:
    twenty_minutes_in_seconds = 20 * 60
    return (end_date - start_date) < twenty_minutes_in_seconds


def process_with_id_batching_only(security_headers: dict, ids: list, start_date: int, end_date: int) -> list:
    id_batches = create_id_batches(ids, batch_size=10)
    logger.info("Created %d ID batches of size 10", len(id_batches))
    return fetch_all_id_batches(security_headers, id_batches, start_date, end_date)


def process_with_id_and_time_batching(security_headers: dict, ids: list, start_date: int, end_date: int) -> list:
    id_batches = create_id_batches(ids, batch_size=1)
    time_chunks = create_daily_time_chunks(start_date, end_date)
    total_requests = len(id_batches) * len(time_chunks)
    logger.info("Created %d ID batches (size 1) × %d time chunks = %d total requests",
                len(id_batches), len(time_chunks), total_requests)
    return fetch_all_batch_combinations(security_headers, id_batches, time_chunks)


def create_id_batches(ids: list, batch_size: int) -> list[list]:
    return [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]


def create_hourly_time_chunks(start_date: int, end_date: int) -> list[tuple[int, int]]:
    one_hour_in_seconds = 3600
    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + one_hour_in_seconds, end_date)
        chunks.append((current_start, current_end))
        current_start = current_end

    return chunks


def create_daily_time_chunks(start_date: int, end_date: int) -> list[tuple[int, int]]:
    one_day_in_seconds = 86400
    chunks = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + one_day_in_seconds, end_date)
        chunks.append((current_start, current_end))
        current_start = current_end

    return chunks


def fetch_all_id_batches(security_headers: dict, id_batches: list[list], start_date: int, end_date: int) -> list:
    responses = []
    total_batches = len(id_batches)

    for batch_idx, id_batch in enumerate(id_batches, 1):
        logger.info("Processing ID batch %d/%d (IDs: %s)", batch_idx, total_batches, len(id_batch))
        response = _acsnservice_fetch(security_headers, id_batch, start_date, end_date)
        responses.append(response)

        if not status_code_success(response.status_code):
            logger.warning("Request failed with status %d, stopping batch processing", response.status_code)
            break

    logger.info("Completed %d ID batch requests", len(responses))
    return responses


def fetch_all_batch_combinations(security_headers: dict, id_batches: list[list],
                                 time_chunks: list[tuple[int, int]]) -> list:
    responses = []
    total_requests = len(id_batches) * len(time_chunks)
    current_request = 0

    for id_batch_idx, id_batch in enumerate(id_batches, 1):
        logger.info("Processing ID batch %d/%d", id_batch_idx, len(id_batches))

        for chunk_idx, (chunk_start, chunk_end) in enumerate(time_chunks, 1):
            current_request += 1
            logger.info("  Time chunk %d/%d (request %d/%d)",
                        chunk_idx, len(time_chunks), current_request, total_requests)
            response = _acsnservice_fetch(security_headers, id_batch, chunk_start, chunk_end)
            responses.append(response)

            if not status_code_success(response.status_code):
                logger.warning("Request failed with status %d, stopping batch processing", response.status_code)
                return responses

    logger.info("Completed all %d combined batch requests", total_requests)
    return responses


def find_first_failed_response(responses: list):
    for response in responses:
        if not status_code_success(response.status_code):
            return response
    return None


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
