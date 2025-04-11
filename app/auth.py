import os
import json
import logging
import functools

logger = logging.getLogger(__name__)


def api_auth_required(func):
    """
    Decorator to validate API authorization code in request headers.
    Checks for x-api-code header and validates it against API_SECRET env variable.
    """

    @functools.wraps(func)
    def wrapper(event, context):
        api_secret = os.environ.get('API_SECRET')
        if not api_secret:
            logger.error("API_SECRET environment variable is not set")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Server configuration error"})
            }

        headers = event.get('headers', {})
        if not headers:
            logger.warning("No headers found in request")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"})
            }

        api_code = None
        for key, value in headers.items():
            if key.lower() == 'x-api-code':
                api_code = value
                break

        if not api_code:
            logger.warning("No x-api-code header found in request")
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Unauthorized"})
            }

        if api_code != api_secret:
            logger.warning("Invalid API code provided")
            return {
                "statusCode": 403,
                "body": json.dumps({"error": "Forbidden"})
            }

        return func(event, context)

    return wrapper
