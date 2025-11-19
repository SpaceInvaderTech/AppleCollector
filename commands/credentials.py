from app.haystack import get_headers
from app.credentials.api import api_credentials_service
from app.models import ICloudCredentials
from app.settings import settings
import logging

logger = logging.getLogger(__name__)

def refresh_credentials_on_aws(schedule_location_fetching: bool = True):
    """
    This function must be invoked on a MacOS device to refresh the credentials.
    """
    _security_headers = get_headers(decryption_key=settings.PASSWD)
    logger.info("Security headers generated successfully.")

    api_credentials_service.update_credentials(
        credentials=ICloudCredentials(**_security_headers),
        schedule_data_fetching=schedule_location_fetching)
    logger.info("Security headers updated successfully.")


if __name__ == "__main__":
    security_headers = get_headers(decryption_key=settings.PASSWD)
    logger.info("Security headers generated successfully.")
    api_credentials_service.update_credentials(ICloudCredentials(**security_headers))
    logger.info("Security headers updated successfully.")
