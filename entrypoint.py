from app.auth import api_auth_required
from app.credentials import service as credentials_service
from app.models import ICloudCredentials
import logging
from app.helpers import lambda_exception_handler
import json

logger = logging.getLogger(__name__)


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
    credentials = ICloudCredentials(**body)
    client_id = event['pathParameters']['client_id']

    logger.info(f"Received credentials: {credentials} for client_id: {client_id}")
    credentials_service.update_credentials(client_id, credentials)

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
        "body": credentials.model_dump_json() if credentials else json.dumps(
            {"error": "Credentials not found"})
    }
