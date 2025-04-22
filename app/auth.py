import os
import json
import logging
import functools

from app.settings import settings

logger = logging.getLogger(__name__)


def api_auth_required(func):
    """
    Decorator to validate API authorization code in request headers.
    Checks for x-api-key header and validates it against CREDENTIALS_API_KEY env variable.
    """

    @functools.wraps(func)
    def wrapper(event, context):
        headers = event.get('headers', {})
        if not headers:
            logger.warning("No headers found in request")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"})
            }

        api_code = None
        for key, value in headers.items():
            if key.lower() == 'x-api-key':
                api_code = value
                break

        if not api_code:
            logger.warning("No x-api-key header found in request")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"})
            }

        if api_code != settings.CREDENTIALS_API_KEY:
            logger.warning("Invalid API code provided")
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Forbidden"})
            }

        return func(event, context)

    return wrapper
