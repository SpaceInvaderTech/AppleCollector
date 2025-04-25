from pydantic import BaseModel
import os
from requests import Session

requestSession = Session()


class CredentialsRetriever(BaseModel):
    base_url: str = 'https://ghfbaqjy00.execute-api.eu-central-1.amazonaws.com/prod/credentials'
    default_client: str = 'space-invader-mac'

    def get_headers(self, api_key: str) -> dict:
        response = requestSession.get(
            url=f'{self.base_url}/{self.default_client}',
            headers={
                'x-api-key': api_key
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to retrieve credentials: {response.status_code} - {response.text}")
        return response.json()

    def put_headers(self, headers: dict, api_key: str, schedule_data_fetching: bool = True) -> None:
        response = requestSession.put(
            url=f'{self.base_url}/{self.default_client}',
            headers={
                'x-api-key': api_key
            },
            json={
                'headers': headers,
                'schedule_data_fetching': schedule_data_fetching
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to update credentials: {response.status_code} - {response.text}")


credentials_retriever = CredentialsRetriever()
