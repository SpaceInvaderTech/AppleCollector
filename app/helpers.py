import functools
import time
from itertools import islice
import logging
import json
from functools import wraps
from pydantic import ValidationError
import traceback

from app.exceptions import AppleAuthCredentialsExpired

logger = logging.getLogger()


def status_code_success(status_code):
    return 200 <= status_code < 300


def chunks(data, step):
    if isinstance(data, dict):
        data_iterable = iter(data)
        for _ in range(0, len(data), step):
            yield {k: data[k] for k in islice(data_iterable, step)}
    elif isinstance(data, list):
        for i in range(0, len(data), step):
            yield data[i: i + step]


def lambda_exception_handler(func):
    @wraps(func)
    def wrapper(event, context):
        try:
            return func(event, context)
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            logger.error(f"Validation Error: {str(e)}")
            return {
                "statusCode": 422,
                "body": json.dumps({
                    "error": "Invalid request data",
                    "detail": e.errors()
                })
            }
        except Exception:
            raise

    return wrapper


def retry_on_apple_auth_expired(credential_refresh_func=None, max_retries=7, backoff_times=None):
    """
    Decorator to retry a function when AppleAuthCredentialsExpired is raised.
    Uses the provided function to refresh credentials before each retry.

    Args:
        credential_refresh_func: Function that returns fresh ICloudCredentials instance
                                (can be a lambda that includes all necessary transformations)
        max_retries: Maximum number of retry attempts
        backoff_times: List of wait times in seconds for each retry attempt
                       Default: [15, 30, 60, 120, 300, 600, 900] (15s to 15m)
    """
    if backoff_times is None:
        backoff_times = [15, 30, 60, 120, 300, 600, 900]  # 15s, 30s, 1m, 2m, 5m, 10m, 15m

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from app.exceptions import AppleAuthCredentialsExpired

            attempt = 0
            while attempt <= max_retries:
                try:
                    return func(*args, **kwargs)
                except AppleAuthCredentialsExpired as e:
                    attempt += 1
                    if attempt > max_retries:
                        logger.error(f"Max retry attempts ({max_retries}) reached for {func.__name__}.")
                        raise  # Re-raise the exception after all retries fail

                    # Refresh credentials using the provided function
                    if credential_refresh_func:
                        fresh_credentials = credential_refresh_func()
                        logger.info("Credentials refreshed after AppleAuthCredentialsExpired.")

                        # Update the credentials in kwargs
                        if 'security_headers' in kwargs:
                            kwargs['security_headers'] = fresh_credentials
                        elif 'headers' in kwargs:
                            kwargs['headers'] = fresh_credentials

                    wait_time = backoff_times[min(attempt - 1, len(backoff_times) - 1)]
                    logger.warning(
                        f"Attempt {attempt}/{max_retries}: AppleAuthCredentialsExpired encountered in {func.__name__}. "
                        f"Retrying in {wait_time} seconds with refreshed credentials. Error: {str(e)}")
                    time.sleep(wait_time)

            return None  # This should not be reached

        return wrapper

    return decorator
