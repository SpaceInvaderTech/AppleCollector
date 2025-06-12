"""
Service for managing credentials in DynamoDB
"""
import os
import boto3
import logging

from app.credentials.base import CredentialsService
from app.models import ICloudCredentials
from app.settings import settings

logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(f"apple-collector-credentials-{os.environ.get('STAGE', 'dev')}")


class DynamoDBCredentialsService(CredentialsService):
    def __init__(self, default_client_id: str):
        self._default_client_id = default_client_id

    def update_credentials(self, credentials: ICloudCredentials, client_id: str = None):
        client_id = client_id if client_id is not None else self._default_client_id

        logger.info(credentials.model_dump())
        table.put_item(Item={
            'id': client_id,
            **credentials.model_dump(exclude_none=False, mode='json', by_alias=True)
        })
        logger.info(f"Saved credentials for client: {client_id}")

    def get_credentials(self, client_id: str = None) -> ICloudCredentials | None:
        client_id = client_id if client_id is not None else self._default_client_id

        try:
            response = table.get_item(Key={'id': client_id})

            if 'Item' not in response:
                logger.info(f"No credentials found for client_id: {client_id}")
                return None

            item = response['Item']
            return ICloudCredentials(**item)
        except Exception as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            return None


dynamodb_credentials_service = DynamoDBCredentialsService(
    default_client_id=settings.DEFAULT_CLIENT_MANAGING_CREDENTIALS)
