"""
Cryptography functions
"""

# pylint: disable=missing-function-docstring

from base64 import b64encode
import hashlib
from codecs import encode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend


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


def unpad(padded_binary, blocksize):
    unpadder = PKCS7(blocksize).unpadder()
    return unpadder.update(padded_binary) + unpadder.finalize()


def get_public_key(priv):
    return (
        ec.derive_private_key(priv, ec.SECP224R1(), default_backend())
        .public_key()
        .public_numbers()
        .x
    )


def get_public_from_private(private_key):
    return int_to_bytes(get_public_key(bytes_to_int(private_key)), 28)


def get_hashed_public_key(private_key):
    return sha256(get_public_from_private(private_key))


def b64_ascii(encodable):
    return b64encode(encodable).decode("ascii")


def get_result(priv, data):
    # Some iOS versions may send messages a bit differently. If we have more than 88 bytes in our message,
    # we need to compensate and adjust where key and data start and end.
    # https://github.com/MatthewKuKanich/FindMyFlipper/issues/61#issuecomment-2065364739
    adj = len(data) - 88
    eph_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP224R1(), data[5+adj:62+adj])
    shared_key = ec.derive_private_key(priv, ec.SECP224R1(), default_backend()).exchange(ec.ECDH(), eph_key)
    symmetric_key = sha256(shared_key + b'\x00\x00\x00\x01' + data[5+adj:62+adj])
    decryption_key = symmetric_key[:16]
    iv = symmetric_key[16:]
    enc_data = data[62+adj:72+adj]
    tag = data[72+adj:]
    return decrypt(enc_data, algorithms.AES(decryption_key), modes.GCM(iv, tag))
