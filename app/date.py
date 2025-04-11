"""
Date helper functions
"""

# pylint: disable=missing-function-docstring

from datetime import datetime
from time import tzname

# number of seconds between 1/1/1970 and 1/1/2001
EPOCH_DIFF = 978307200


def unix_epoch():
    return int(datetime.now().strftime("%s"))


def get_utc_time():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_timezone():
    return tzname[1]


def date_milliseconds(date):
    return date * 1000
