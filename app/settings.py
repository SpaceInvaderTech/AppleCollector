from pydantic import BaseModel
from pydantic.v1 import BaseSettings


class Headers(BaseModel):
    x_api_key: str

    def model_dump(self, **kwargs):
        return {
            # "X-API-Key": self.x_api_key
            "x-api-key": self.x_api_key
        }


class Settings(BaseSettings):
    BASE_URL: str = "https://beam-api.spaceinvader.com"
    API_KEY: str
    HAYSTACKS_ENDPOINT: str = '/haystacks'
    PASSWD: str
    USER_AGENT_COMMENT: str = "Beam API"
    DEVICE_BATCH_SIZE: int = 10
    CREDENTIALS_API_KEY: str

    SENTRY_ENABLED: bool = True
    SENTRY_ENV: str = "local"
    SENTRY_DSN: str = ""

    DEFAULT_CLIENT_MANAGING_CREDENTIALS: str = 'space-invader-mac'

    @property
    def get_haystacks_endpoint(self) -> str:
        return f'{self.BASE_URL}/{self._get_haystack_endpoint_without_prefix()}'

    @property
    def post_haystacks_endpoint(self) -> str:
        return f'{self.BASE_URL}/{self._get_haystack_endpoint_without_prefix()}'

    @property
    def headers(self) -> dict:
        return Headers(x_api_key=self.API_KEY).model_dump()

    def _get_haystack_endpoint_without_prefix(self,) -> str:
        endpoint = self.HAYSTACKS_ENDPOINT
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        return endpoint

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
