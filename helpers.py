"""
Helper functions
"""

# pylint: disable=missing-function-docstring

from os import path, environ
from glob import glob
from base64 import b64decode, b64encode
import hashlib
import hmac
from codecs import encode
import struct
from itertools import islice
from requests import Session
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from objc import loadBundleFunctions
from Foundation import NSBundle, NSClassFromString, NSData, NSPropertyListSerialization
from date import unix_epoch, get_utc_time, get_timezone, date_milliseconds


requestSession = Session()


def int_to_bytes(n, length, endianess="big"):
    return int.to_bytes(n, length, endianess)


def bytes_to_int(b):
    return int(encode(b, "hex"), 16)


def sha256(data):
    digest = hashlib.new("sha256")
    digest.update(data)
    return digest.digest()


def decrypt(enc_data, algorithm_dkey, mode):
    decryptor = Cipher(algorithm_dkey, mode, default_backend()).decryptor()
    return decryptor.update(enc_data) + decryptor.finalize()


def unpad(paddedBinary, blocksize):
    unpadder = PKCS7(blocksize).unpadder()
    return unpadder.update(paddedBinary) + unpadder.finalize()


def decode_tag(data):
    latitude = struct.unpack(">i", data[0:4])[0] / 10000000.0
    longitude = struct.unpack(">i", data[4:8])[0] / 10000000.0
    confidence = bytes_to_int(data[8:9])
    status = bytes_to_int(data[9:10])
    return {"lat": latitude, "lon": longitude, "conf": confidence, "status": status}


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


def get_public_key(priv):
    return (
        ec.derive_private_key(priv, ec.SECP224R1(), default_backend())
        .public_key()
        .public_numbers()
        .x
    )


def getHeaders(iCloud_decryptionkey):
    AppleDSID, searchPartyToken = getAppleDSIDandSearchPartyToken(iCloud_decryptionkey)
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


def acsnservice_fetch(decryptionkey, ids, startdate, enddate):
    data = {
        "search": [
            {
                "startDate": date_milliseconds(startdate),
                "endDate": date_milliseconds(enddate),
                "ids": ids,
            }
        ]
    }
    return requestSession.post(
        "https://gateway.icloud.com/acsnservice/fetch",
        headers=getHeaders(decryptionkey),
        json=data,
        timeout=60,
    )


def status_code_success(status_code):
    return 200 <= status_code < 300


def get_public_from_private(private_key):
    return int_to_bytes(get_public_key(bytes_to_int(private_key)), 28)


def get_hashed_public_key(private_key):
    return sha256(get_public_from_private(private_key))


def b64_ascii(encodable):
    return b64encode(encodable).decode("ascii")


def chunks(data, step):
    data_iterable = iter(data)
    for _ in range(0, len(data), step):
        yield {k: data[k] for k in islice(data_iterable, step)}


# @see https://github.com/hatomist/openhaystack-python
def get_result(priv, data):
    eph_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP224R1(), data[5:62])
    shared_key = ec.derive_private_key(
        priv, ec.SECP224R1(), default_backend()
    ).exchange(ec.ECDH(), eph_key)
    symmetric_key = sha256(shared_key + b"\x00\x00\x00\x01" + data[5:62])
    decryption_key = symmetric_key[:16]
    iv = symmetric_key[16:]
    enc_data = data[62:72]
    tag = data[72:]
    decrypted = decrypt(enc_data, algorithms.AES(decryption_key), modes.GCM(iv, tag))
    return decode_tag(decrypted)
