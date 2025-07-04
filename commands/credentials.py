from app.haystack import get_headers
from app.credentials.api import api_credentials_service
from app.settings import settings
import logging

logger = logging.getLogger(__name__)

security_headers = get_headers(decryption_key=settings.PASSWD)
logger.info("Security headers generated successfully.")
api_credentials_service.update_credentials(security_headers, api_key=settings.CREDENTIALS_API_KEY)
logger.info("Security headers updated successfully.")


def refresh_credentials_on_aws(schedule_location_fetching: bool = True):
    """
    This function must be invoked on a MacOS device to refresh the credentials.
    """
    security_headers = get_headers(decryption_key=settings.PASSWD)
    logger.info("Security headers generated successfully.")

    api_credentials_service.update_credentials(
        headers=security_headers,
        api_key=settings.CREDENTIALS_API_KEY,
        schedule_data_fetching=schedule_location_fetching)
    logger.info("Security headers updated successfully.")
