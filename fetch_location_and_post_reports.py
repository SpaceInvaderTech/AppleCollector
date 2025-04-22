from app.models import ICloudCredentials
from app.settings import settings
import json
from app.device_service import fetch_and_report_locations_for_devices
from app.http_credentials import credentials_retriever
import logging.config

logger = logging.getLogger(__name__)
with open('app/logging.json', 'rt') as f:
    config = json.load(f)
    logging.config.dictConfig(config)

if __name__ == "__main__":
    security_headers = credentials_retriever.get_headers(api_key=settings.CREDENTIALS_API_KEY)
    logger.info("Security headers retrieved successfully.")

    fetch_and_report_locations_for_devices(ICloudCredentials(**security_headers), 0)
