import logging

from app.credentials.base import CredentialsService
from app.dtos import BeamerDevice, BeamLocationReports, LocalFetchResult, LocationReport
from app.device_service import fetch_and_report_locations_for_devices, fetch_all_reports_for_devices, fetch_devices
from app.credentials.api import api_credentials_service
from app.key_cache import KeyCache

logger = logging.getLogger(__name__)


def resolve_locations(
        tracker_ids: set[str] = None,
        limit: int = 2500,
        page: int | None = None,
        send_reports: bool = True,
        minutes_ago: int = 15,
        print_report: bool = False,
        credentials_service: CredentialsService = api_credentials_service,
) -> None:
    devices: list[BeamerDevice] = fetch_and_report_locations_for_devices(
        credentials_service=credentials_service,
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


def collect_all_reports(
        credentials_service: CredentialsService,
        tracker_ids: set[str] | None,
        minutes_ago: int,
        limit: int = 2500,
        page: int | None = None,
        key_cache_path: str | None = None,
        refresh_keys: bool = False,
) -> LocalFetchResult:
    """Every report per beam in the time range. Never posts anything to the API."""
    if key_cache_path:
        cache = KeyCache(path=key_cache_path, download=lambda: fetch_devices(limit))
        devices = cache.get_devices(tracker_ids, refresh=refresh_keys)
    else:
        devices = [d for d in fetch_devices(limit, page=page) if not tracker_ids or d.name in tracker_ids]

    reports = fetch_all_reports_for_devices(credentials_service, devices, minutes_ago)
    requested = sorted(tracker_ids or [])
    found = {d.name for d in devices}
    return LocalFetchResult(
        beams=[
            BeamLocationReports(
                name=d.name,
                id=d.id,
                reports=[LocationReport.model_validate(r.model_dump()) for r in reports.get(d.id, [])],
            )
            for d in devices
        ],
        requested=requested,
        missing=[name for name in requested if name not in found],
    )
