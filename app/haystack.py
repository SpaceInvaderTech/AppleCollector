"""
Haystack functions
"""

# pylint: disable=missing-function-docstring

from os import path, environ
from glob import glob
from base64 import b64decode, b64encode
import hashlib
import hmac
from cryptography.hazmat.primitives.ciphers import algorithms, modes
from objc import loadBundleFunctions
from Foundation import NSBundle, NSClassFromString, NSData, NSPropertyListSerialization
from app.date import unix_epoch, get_utc_time, get_timezone
from app.cryptic import bytes_to_int, decrypt, unpad


# copied from https://github.com/Hsn723/MMeTokenDecrypt
def getAppleDSIDandSearchPartyToken(iCloudKey):
    decryption_key = hmac.new(
        b"t9s\"lx^awe.580Gj%'ld+0LG<#9xa?>vb)-fkwb92[}",
        b64decode(iCloudKey),
        digestmod=hashlib.md5,
    ).digest()
    mmeTokenFile = glob(
        "%s/Library/Application Support/iCloud/Accounts/[0-9]*" % path.expanduser("~")
    )[0]
    decryptedBinary = unpad(
        decrypt(
            open(mmeTokenFile, "rb").read(),
            algorithms.AES(decryption_key),
            modes.CBC(b"\00" * 16),
        ),
        algorithms.AES.block_size,
    )
    binToPlist = NSData.dataWithBytes_length_(decryptedBinary, len(decryptedBinary))
    tokenPlist = NSPropertyListSerialization.propertyListWithData_options_format_error_(
        binToPlist, 0, None, None
    )[0]
    return (
        tokenPlist["appleAccountInfo"]["dsPrsID"],
        tokenPlist["tokens"]["searchPartyToken"],
    )


def getOTPHeaders():
    AOSKitBundle = NSBundle.bundleWithPath_(
        "/System/Library/PrivateFrameworks/AOSKit.framework"
    )
    loadBundleFunctions(AOSKitBundle, globals(), [("retrieveOTPHeadersForDSID", b"")])
    util = NSClassFromString("AOSUtilities")
    anisette = (
        str(util.retrieveOTPHeadersForDSID_("-2"))
        .replace('"', " ")
        .replace(";", " ")
        .split()
    )
    return anisette[6], anisette[3]


def get_headers(decryption_key) -> dict:
    AppleDSID, searchPartyToken = getAppleDSIDandSearchPartyToken(decryption_key)
    machineID, oneTimePassword = getOTPHeaders()
    UTCTime = get_utc_time()
    Timezone = get_timezone()
    USER_AGENT_COMMENT = environ.get("USER_AGENT_COMMENT", "")
    return {
        "User-Agent": "SpaceInvader/AppleCollector %s" % (USER_AGENT_COMMENT),
        "Accept": "application/json",
        "Authorization": "Basic %s"
        % (
            b64encode((AppleDSID + ":" + searchPartyToken).encode("ascii")).decode(
                "ascii"
            )
        ),
        "X-Apple-I-MD": "%s" % (oneTimePassword),
        "X-Apple-I-MD-RINFO": "17106176",
        "X-Apple-I-MD-M": "%s" % (machineID),
        "X-Apple-I-TimeZone": "%s" % (Timezone),
        "X-Apple-I-Client-Time": "%s" % (UTCTime),
        "X-BA-CLIENT-TIMESTAMP": "%s" % (unix_epoch()),
    }
