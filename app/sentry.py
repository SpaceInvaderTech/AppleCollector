import logging
import sentry_sdk
from app.settings import settings

logger = logging.getLogger(__name__)


def _initialize_sentry(
        environment: str,
        sentry_dsn: str,
        release: str = None,
):
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment.lower(),
        release=release,
        enable_tracing=False,
        traces_sample_rate=0.0,
        profiles_sample_rate=0.0,
        ignore_errors=[],
    )


def setup_sentry():
    if settings.SENTRY_ENABLED:
        logger.info('***** Initializing sentry *****')
        _initialize_sentry(
            settings.SENTRY_ENV,
            settings.SENTRY_DSN,
        )
        logger.info('***** Sentry initialized: %s *****', sentry_sdk.is_initialized())
