import random
import sys
from time import sleep

from app.sentry import setup_sentry
import json
import logging.config
import click

try:
    # Wrap credentials import in try-except, to allow running from non-Mac devices
    from commands.credentials import refresh_credentials_on_aws
except ImportError:
    print("Failed to import credentials module", file=sys.stderr)

from app.credentials.api import api_credentials_service
from commands.location_and_reports import collect_all_reports, resolve_locations

setup_sentry()
logger = logging.getLogger(__name__)
with open('app/logging.json', 'rt') as f:
    config = json.load(f)
    logging.config.dictConfig(config)


@click.group()
def cli():
    """Main entry point for the CLI."""
    pass


MAX_MINUTES_AGO = 7 * 24 * 60


def _validate_minutes_ago(ctx, param, value: int) -> int:
    if value < 1:
        raise click.BadParameter('must be at least 1')
    if value > MAX_MINUTES_AGO:
        raise click.BadParameter(f'must be at most {MAX_MINUTES_AGO} (7 days); Apple keeps reports for about 7 days')
    return value


def _log_to_stderr() -> None:
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setStream(sys.stderr)


@cli.command()
@click.option(
    '--trackers', '-t', default='',
    help='Comma-separated list of trackers. E.g: E0D4FA128FA9,EC3987ECAA50,CDAA0CCF4128,EDDC7DA1A247,D173D540749D'
)
@click.option('--limit', '-l', default=2500, help='Number of locations to fetch')
@click.option('--page', '-p', type=int, default=None, help='Only fetch this 1-based page (default: all pages)')
@click.option('--minutes-ago', '-ma', default=24, callback=_validate_minutes_ago,
              help=f'Number of minutes ago to fetch locations for (max {MAX_MINUTES_AGO})')
@click.option('--send-reports', '-s', is_flag=True, default=False, help='Whether to send reports')
@click.option('--output', type=click.Choice(['text', 'json']), default='text',
              help='json: print every report per beam as one JSON document on stdout; logs go to stderr')
@click.option('--local-credentials', is_flag=True, default=False,
              help="Read Apple credentials from this Mac's Keychain instead of the shared AWS record")
@click.option('--key-cache', type=click.Path(dir_okay=False), default=None,
              help='Encrypted local cache of beam keys, refreshed when older than 24 h or a tracker is missing')
@click.option('--refresh-keys', is_flag=True, default=False, help='Download the key cache again before fetching')
def fetch_locations(
        trackers: str,
        limit: int,
        page: int | None,
        send_reports: bool,
        minutes_ago: int,
        output: str,
        local_credentials: bool,
        key_cache: str | None,
        refresh_keys: bool,
) -> None:
    if output == 'json':
        _log_to_stderr()
    if refresh_keys and not key_cache:
        raise click.UsageError('--refresh-keys needs --key-cache')
    if key_cache and page is not None:
        raise click.UsageError('--page cannot be combined with --key-cache')
    if send_reports and (output == 'json' or key_cache):
        raise click.UsageError('--send-reports cannot be combined with --output json or --key-cache')

    tracker_ids = set(trackers.split(',')) if trackers else None
    if local_credentials:
        from app.credentials.keychain import KeychainCredentialsService
        credentials_service = KeychainCredentialsService()
    else:
        credentials_service = api_credentials_service

    if output == 'text' and not key_cache:
        resolve_locations(
            tracker_ids=tracker_ids,
            limit=limit,
            page=page,
            send_reports=send_reports,
            minutes_ago=minutes_ago,
            print_report=True,
            credentials_service=credentials_service,
        )
        return

    result = collect_all_reports(
        credentials_service=credentials_service,
        tracker_ids=tracker_ids,
        minutes_ago=minutes_ago,
        limit=limit,
        page=page,
        key_cache_path=key_cache,
        refresh_keys=refresh_keys,
    )
    if output == 'json':
        click.echo(result.model_dump_json())
        return
    for beam in result.beams:
        logger.info(f"{beam.name} ({beam.id}): {len(beam.reports)} reports")
        for report in beam.reports:
            logger.info(f"  {report}")
    if result.missing:
        logger.info(f"Missing trackers: {','.join(result.missing)}")


@cli.command()
@click.option('--schedule-location-fetching', '-s', is_flag=True, default=False, help='Schedule location fetching')
def refresh_credentials(schedule_location_fetching: bool) -> None:
    refresh_credentials_on_aws(
        schedule_location_fetching=schedule_location_fetching,
    )
    if schedule_location_fetching:
        times_to_refresh = 5
        for _ in range(times_to_refresh):
            time_to_wait = 50 + random.randint(0, 9)
            click.echo(
                f'Refreshing credentials in {time_to_wait} seconds to avoid AppleAuthCredentialsExpired exception')
            sleep(time_to_wait)
            refresh_credentials_on_aws(schedule_location_fetching=False)


if __name__ == '__main__':
    cli()
