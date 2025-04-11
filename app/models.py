from pydantic import BaseModel
from datetime import datetime


class ICloudCredentials(BaseModel):
    icloud_key: str
    apple_dsid: str
    search_party_token: str
    machine_id: str
    timezone: str
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
