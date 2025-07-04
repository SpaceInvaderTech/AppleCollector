from pydantic import BaseModel
import os
from requests import Session

from app.credentials.base import CredentialsService
from app.models import ICloudCredentials
from app.settings import settings

requestSession = Session()


class APICredentialsService(CredentialsService):
    def __init__(
        self,
        api_key: str,
        base_url: str = 'https://ghfbaqjy00.execute-api.eu-central-1.amazonaws.com/prod/credentials',
        default_client: str = 'space-invader-mac'
    ):
        self.base_url = base_url
        self.default_client = default_client
        self.api_key = api_key

    def get_credentials(self) -> ICloudCredentials:
        response = requestSession.get(
            url=f'{self.base_url}/{self.default_client}',
            headers={
                'x-api-key': self.api_key
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to retrieve credentials: {response.status_code} - {response.text}")
        return ICloudCredentials(**response.json())

    def update_credentials(self, credentials: ICloudCredentials, schedule_data_fetching: bool = True) -> None:
        response = requestSession.put(
            url=f'{self.base_url}/{self.default_client}',
            headers={
                'x-api-key': self.api_key
            },
            json={
                'headers': credentials.model_dump(by_alias=True),
                'schedule_data_fetching': schedule_data_fetching
            }
        )
        if response.status_code != 200:
            raise Exception(f"Failed to update credentials: {response.status_code} - {response.text}")


api_credentials_service = APICredentialsService(api_key=settings.CREDENTIALS_API_KEY)

