from app.cryptic import b64_ascii, bytes_to_int, get_hashed_public_key
from pydantic import BaseModel, Field, computed_field
from typing import List


class Report(BaseModel):
    lat: float
    lon: float
    conf: float = Field(..., description="Confidence score between 0 and 1")
    status: int


class EnrichedReport(Report):
    device_id: str
    timestamp: int
    date_published: int
    description: str


class PrivateKey(BaseModel):
    type: str
    data: List[int]


class BeamerDevice(BaseModel):
    """
    Example:
    {
        "id": "9ed47345-fe98-460b-b390-2d9026c89aaa",
        "name": "E955EC5E659E",
        "privateKey": {
            "type": "Buffer",
            "data": [
                226, 167, 150, 255, 228, 36, 61, 116,
                74, 179, 188, 216, 66, 184, 166, 15,
                5, 119, 42, 188, 67, 149, 246, 123,
                85, 183, 1, 52
            ]
        }
    }
    """
    id: str
    name: str
    privateKey: PrivateKey
    report: EnrichedReport | None = None

    @computed_field
    @property
    def private_key_bytes(self) -> bytes:
        return bytes(self.privateKey.data)

    @computed_field
    @property
    def public_hash_base64(self) -> str:
        return b64_ascii(get_hashed_public_key(self.private_key_bytes))

    @computed_field
    @property
    def private_key_numeric(self) -> str:
        return bytes_to_int(self.private_key_bytes)


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int
    pageCount: int


class DeviceResponse(BaseModel):
    data: list[BeamerDevice]
    meta: PaginationMeta


class HaystackReport(BaseModel):
    timestamp: int
    lat: float
    lon: float
    conf: float


class HaystackSignalInput(BaseModel):
    id: str
    name: str
    report: HaystackReport

    @staticmethod
    def get_haystack_signal_from_device(device: BeamerDevice) -> 'HaystackSignalInput':
        return HaystackSignalInput(
            id=device.id,
            name=device.name,
            report=HaystackReport(
                timestamp=device.report.timestamp,
                lat=device.report.lat,
                lon=device.report.lon,
                conf=device.report.conf
            )
        )
