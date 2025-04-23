import os
from app.auth import api_auth_required
from app.device_service import fetch_and_report_locations_for_devices
from app.credentials import service as credentials_service
from app.dtos import PutHeadersBody
import logging
from app.helpers import lambda_exception_handler
import json
from app.sentry import setup_sentry
from app.settings import settings
from app.sqs import schedule_device_location_metadata_enrichment

logger = logging.getLogger(__name__)
default_client: str = 'space-invader-mac'
setup_sentry()


@lambda_exception_handler
@api_auth_required
def put_credentials(event, context):
    if 'body' not in event or not event['body']:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing request body"})
        }
    if 'pathParameters' not in event or not event['pathParameters'] or 'client_id' not in event['pathParameters']:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing client_id in path parameters"})
        }
    body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']

    body = PutHeadersBody(**body)
    client_id = event['pathParameters']['client_id']

    logger.info(f"Received credentials: {body.headers} for client_id: {client_id}")
    credentials_service.update_credentials(client_id, body.headers)
    if body.schedule_data_fetching:
        logger.info("Scheduling data fetching...")
        schedule_device_location_metadata_enrichment(
            os.environ.get('QUEUE_URL'),
            num_batches=1,
            batch_size=settings.DEVICE_BATCH_SIZE
        )

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Credentials updated successfully"})
    }


@lambda_exception_handler
@api_auth_required
def get_credentials(event, context):
    if 'pathParameters' not in event or not event['pathParameters'] or 'client_id' not in event['pathParameters']:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing client_id in path parameters"})
        }
    client_id = event['pathParameters']['client_id']

    credentials = credentials_service.get_credentials(client_id)

    return {
        "statusCode": 200,
        "body": credentials.model_dump_json(by_alias=True, indent=2) if credentials else json.dumps(
            {"error": "Credentials not found"})
    }


@lambda_exception_handler
def fetch_locations_and_report(event, context):
    if 'Records' not in event or not event['Records']:
        logger.error("No records found in SQS event")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No SQS records found in event"})
        }

    # Process the first record (since batch size = 1)
    record = event['Records'][0]
    message_body = json.loads(record['body'])
    try:
        page = int(message_body['page'])
        limit = int(message_body['limit'])
        hours_ago = int(message_body.get('hours_ago', 1))
    except (ValueError, TypeError):
        logger.error(f"Invalid page value: {message_body['page']}. Must be an integer.")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Page value must be an integer"})
        }

    logger.info(f"Processing page: {page}")
    security_headers = credentials_service.get_credentials(settings.DEFAULT_CLIENT_MANAGING_CREDENTIALS)
    fetch_and_report_locations_for_devices(
        security_headers,
        page=page,
        limit=limit,
        hours_ago=hours_ago)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": f"Successfully processed page {page}"})
    }
