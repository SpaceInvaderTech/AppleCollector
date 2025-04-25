"""
Service for managing credentials in DynamoDB
"""
import os
import boto3
import logging

from app.models import ICloudCredentials

logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(f"apple-collector-credentials-{os.environ.get('STAGE', 'dev')}")


class CredentialsService:
    def update_credentials(self, client_id: str, credentials: ICloudCredentials):
        logger.info(credentials.model_dump())
        table.put_item(Item={
            'id': client_id,
            **credentials.model_dump(exclude_none=False, mode='json', by_alias=True)
        })
        logger.info(f"Saved credentials for client: {client_id}")

    def get_credentials(self, client_id: str) -> ICloudCredentials | None:
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


service = CredentialsService()
