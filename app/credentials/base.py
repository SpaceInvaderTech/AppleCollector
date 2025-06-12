import abc

from app.models import ICloudCredentials


class CredentialsService:
    @abc.abstractmethod
    def update_credentials(self, credentials: ICloudCredentials):
        pass

    @abc.abstractmethod
    def get_credentials(self) -> ICloudCredentials | None:
        pass
