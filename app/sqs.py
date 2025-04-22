import uuid
import boto3
import json

sqs = boto3.client('sqs')


def schedule_5_batches_of_600_devices_for_location_retrieval(queue_url: str):
    for page in range(5):
        message = {
            "page": page
        }
        message_group_id = f'page-processing-group_{str(uuid.uuid4())}'

        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=message_group_id,
        )
        print(f"Sent message for page {page}, MessageId: {response['MessageId']}")

    print("All messages sent successfully!")
