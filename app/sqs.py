import uuid
import boto3
import json

sqs = boto3.client('sqs')


def schedule_device_location_metadata_enrichment(queue_url: str, batch_size: int) -> None:
    message = {
        "limit": batch_size,
        "minutes_ago": 15,
    }
    message_group_id = f'page-processing-group_{str(uuid.uuid4())}'

    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
        MessageGroupId=message_group_id,
    )
    print(f"Sent message for all pages of {batch_size} devices, MessageId: {response['MessageId']}")
