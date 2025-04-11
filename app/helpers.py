from itertools import islice
import logging
import json
from functools import wraps
from pydantic import ValidationError
import traceback

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
        except Exception as e:
            logger.error(f"Unhandled Exception: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Internal server error",
                    "detail": str(e)
                })
            }

    return wrapper
