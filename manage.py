from app.sentry import setup_sentry
import json
import logging.config
import click

from commands.credentials import refresh_credentials_on_aws
from commands.location_and_reports import resolve_locations

setup_sentry()
logger = logging.getLogger(__name__)
with open('app/logging.json', 'rt') as f:
    config = json.load(f)
    logging.config.dictConfig(config)


@click.group()
def cli():
    """Main entry point for the CLI."""
    pass


@cli.command()
@click.option(
    '--trackers', '-t', default='',
    help='Comma-separated list of trackers. E.g: E0D4FA128FA9,EC3987ECAA50,CDAA0CCF4128,EDDC7DA1A247,D173D540749D'
)
@click.option('--limit', '-l', default=2500, help='Number of locations to fetch')
@click.option('--page', '-p', default=0, help='Page number for pagination')
@click.option('--minutes-ago', '-ma', default=24, help='Number of minutes ago to fetch locations for')
@click.option('--send-reports', '-s', is_flag=True, default=False, help='Whether to send reports')
def fetch_locations(
        trackers: str,
        limit: int,
        page: int,
        send_reports: bool,
        minutes_ago: int
) -> None:
    tracker_ids = set(trackers.split(',')) if trackers else None
    resolve_locations(
        tracker_ids=tracker_ids,
        limit=limit,
        page=page,
        send_reports=send_reports,
        minutes_ago=minutes_ago,
        print_report=True,
    )


@cli.command()
@click.option('--schedule-location-fetching', '-s', is_flag=True, default=False, help='Schedule location fetching')
def refresh_credentials(schedule_location_fetching: bool) -> None:
    refresh_credentials_on_aws(
        schedule_location_fetching=schedule_location_fetching,
    )


if __name__ == '__main__':
    cli()
