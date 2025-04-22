from pydantic import BaseModel, Field
from datetime import datetime


# class ICloudCredentials(BaseModel):
#     icloud_key: str
#     apple_dsid: str
#     search_party_token: str
#     machine_id: str
#     timezone: str
#     timestamp: datetime
#
#     class Config:
#         json_encoders = {
#             datetime: lambda dt: dt.isoformat()
#         }


class ICloudCredentials(BaseModel):
    """Pydantic model for HTTP headers with exact field name preservation."""
    user_agent: str = Field(alias="User-Agent")
    accept: str = Field(alias="Accept")
    authorization: str = Field(alias="Authorization")
    x_apple_i_md: str = Field(alias="X-Apple-I-MD")
    x_apple_i_md_rinfo: str = Field(alias="X-Apple-I-MD-RINFO")
    x_apple_i_md_m: str = Field(alias="X-Apple-I-MD-M")
    x_apple_i_timezone: str = Field(alias="X-Apple-I-TimeZone")
    x_apple_i_client_time: str = Field(alias="X-Apple-I-Client-Time")
    x_ba_client_timestamp: str = Field(alias="X-BA-CLIENT-TIMESTAMP")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True

        # These ensure original field names are preserved in serialization
        alias_generator = None
        validate_by_name = False

        # Crucial for exact serialization with original field names
        alias_priority = 2
