from app.credentials.base import CredentialsService
from app.models import ICloudCredentials
from app.settings import settings


class KeychainCredentialsService(CredentialsService):
    """Reads Apple credentials from this Mac's Keychain on every call. Read-only: never writes to AWS."""

    def get_credentials(self) -> ICloudCredentials:
        from app.haystack import get_headers

        return ICloudCredentials(**get_headers(decryption_key=settings.PASSWD))

    def update_credentials(self, credentials: ICloudCredentials):
        raise NotImplementedError("Keychain credentials are local-only and are never stored")
