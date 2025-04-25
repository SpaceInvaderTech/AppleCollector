from app.haystack import get_headers
from app.http_credentials import credentials_retriever
from app.settings import settings
import logging

logger = logging.getLogger(__name__)

security_headers = get_headers(decryption_key=settings.PASSWD)
logger.info("Security headers generated successfully.")
credentials_retriever.put_headers(security_headers, api_key=settings.CREDENTIALS_API_KEY)
logger.info("Security headers updated successfully.")


def refresh_credentials_on_aws(schedule_location_fetching: bool = True):
    """
    This function must be invoked on a MacOS device to refresh the credentials.
    """
    security_headers = get_headers(decryption_key=settings.PASSWD)
    logger.info("Security headers generated successfully.")

    credentials_retriever.put_headers(
        headers=security_headers,
        api_key=settings.CREDENTIALS_API_KEY,
        schedule_data_fetching=schedule_location_fetching)
    logger.info("Security headers updated successfully.")
