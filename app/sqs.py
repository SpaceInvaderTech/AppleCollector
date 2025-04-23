import uuid
import boto3
import json

sqs = boto3.client('sqs')


def schedule_device_location_metadata_enrichment(
        queue_url: str,
        num_batches: int,
        batch_size: int
) -> None:
    for page in range(num_batches):
        message = {
            "page": page,
            "limit": batch_size,
            "hours_ago": 1,
        }
        message_group_id = f'page-processing-group_{str(uuid.uuid4())}'

        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=message_group_id,
        )
        print(f"Sent message for page {page}, MessageId: {response['MessageId']}")

    print("All messages sent successfully!")
