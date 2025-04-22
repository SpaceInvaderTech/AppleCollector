"""
This script must run on a MacOS system with the iCloud account in the keychain.
"""
from app.haystack import get_headers
from app.http_credentials import credentials_retriever
from app.settings import settings
import logging.config
import json

logger = logging.getLogger(__name__)
with open('app/logging.json', 'rt') as f:
    config = json.load(f)
    logging.config.dictConfig(config)

security_headers = get_headers(decryption_key=settings.PASSWD)
logger.info("Security headers generated successfully.")
credentials_retriever.put_headers(security_headers, api_key=settings.CREDENTIALS_API_KEY)
logger.info("Security headers updated successfully.")
