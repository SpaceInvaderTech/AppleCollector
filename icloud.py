# pylint: disable=missing-function-docstring

from getpass import getpass
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from objc import loadBundleFunctions
from Foundation import NSBundle, NSClassFromString, NSData, NSPropertyListSerialization


def readKeychain():
    # https://github.com/libyal/dtformats/blob/main/documentation/MacOS%20keychain%20database%20file%20format.asciidoc
    res = [None] * 7
    with open(
        "%s/Library/Keychains/login.keychain-db" % path.expanduser("~"), "rb"
    ) as db:
        kc = db.read()

        def get_table_offsets(tbl_array_offset):
            ntables = bytes_to_int(kc[tbl_array_offset + 4 : tbl_array_offset + 8])
            tbl_offsets_b = kc[
                tbl_array_offset + 8 : tbl_array_offset + 8 + (ntables * 4)
            ]
            return [
                bytes_to_int(tbl_offsets_b[i : i + 4]) + tbl_array_offset
                for i in range(0, len(tbl_offsets_b), 4)
            ]

        def get_record_offsets(tbl_start):
            nrecords = bytes_to_int(kc[tbl_start + 24 : tbl_start + 28])
            rec_offsets_b = kc[tbl_start + 28 : tbl_start + 28 + (nrecords * 4)]
            rec_offsets = [
                bytes_to_int(rec_offsets_b[i : i + 4]) + tbl_start
                for i in range(0, len(rec_offsets_b), 4)
            ]
            # remove 0 offset records and empty records
            return [
                ro
                for ro in rec_offsets
                if ro != tbl_start and bytes_to_int(kc[ro : ro + 4])
            ]

        def match_record_attribute(rec_start, rec_nattr, rec_attr, attr_match):
            attr_offsets_b = kc[rec_start + 24 : rec_start + 24 + (rec_nattr * 4)]
            attr_offsets = [
                bytes_to_int(attr_offsets_b[i : i + 4]) + rec_start - 1
                for i in range(0, len(attr_offsets_b), 4)
            ]
            # non-zero offset, and no weird big values
            if attr_offsets[0] and attr_offsets[0] < rec_start + bytes_to_int(
                kc[rec_start : rec_start + 4]
            ):
                if (
                    kc[
                        attr_offsets[rec_attr]
                        + 4 : attr_offsets[rec_attr]
                        + 4
                        + bytes_to_int(
                            kc[attr_offsets[rec_attr] : attr_offsets[rec_attr] + 4]
                        )
                    ]
                    == attr_match
                ):
                    # return record blob data (NOTE not sure about BLOB size!!!)
                    return kc[
                        rec_start
                        + 24
                        + (rec_nattr * 4) : rec_start
                        + 24
                        + (rec_nattr * 4)
                        + bytes_to_int(kc[rec_start + 16 : rec_start + 20])
                    ]
            return None

        if kc[:4] == b"kych":
            tbl_offsets = get_table_offsets(bytes_to_int(kc[12:16]))
            symmetric_key_idx = None
            # walk backwards so we get the generic password blob before the symmetric key, we need that to select which key to take
            for tbl_start in tbl_offsets[::-1]:
                if (
                    kc[tbl_start + 4 : tbl_start + 8] == b"\x00\x00\x00\x11"
                ):  # Symmetric key
                    rec_offsets = get_record_offsets(tbl_start)
                    for rec_start in rec_offsets:
                        # might be wrong about amount of attributes
                        symmetric_key_blob = match_record_attribute(
                            rec_start, 27, 1, symmetric_key_idx
                        )
                        if symmetric_key_blob:
                            start_crypto_blob = bytes_to_int(symmetric_key_blob[8:12])
                            total_length = bytes_to_int(symmetric_key_blob[12:16])
                            res[2] = symmetric_key_blob[16:24]
                            res[3] = symmetric_key_blob[
                                24
                                + (start_crypto_blob - 0x18) : 24
                                + (total_length - 0x18)
                            ]
                            break
                elif (
                    kc[tbl_start + 4 : tbl_start + 8] == b"\x80\x00\x00\x00"
                ):  # Generic passwords
                    rec_offsets = get_record_offsets(tbl_start)
                    for rec_start in rec_offsets:
                        # generic password record has 16 attributes
                        icloud_key_blob = match_record_attribute(
                            rec_start, 16, 14, b"iCloud"
                        )
                        if icloud_key_blob:
                            symmetric_key_idx = icloud_key_blob[:20]
                            res[0] = icloud_key_blob[20:28]
                            res[1] = icloud_key_blob[28:]
                            break
                # Metadata, containing master key and db key
                elif kc[tbl_start + 4 : tbl_start + 8] == b"\x80\x00\x80\x00":
                    rec_start = get_record_offsets(tbl_start)[0]
                    db_key_blob = kc[
                        rec_start
                        + 24 : rec_start
                        + 24
                        + bytes_to_int(kc[rec_start + 16 : rec_start + 20])
                    ]  # 2nd record is the one we want
                    res[4] = db_key_blob[44:64]
                    res[5] = db_key_blob[64:72]
                    res[6] = db_key_blob[120:168]
    return res


def retrieveICloudKey():
    (
        icloud_key_IV,
        icloud_key_enc,
        symmetric_key_IV,
        symmetric_key_enc,
        db_key_salt,
        db_key_IV,
        db_key_enc,
    ) = readKeychain()
    password = getpass("Keychain password:")
    master_key = PBKDF2HMAC(
        algorithm=SHA1(),
        length=24,
        salt=db_key_salt,
        iterations=1000,
        backend=default_backend(),
    ).derive(bytes(password, encoding="ascii"))
    db_key = unpad(
        decrypt(db_key_enc, algorithms.TripleDES(master_key), modes.CBC(db_key_IV)),
        algorithms.TripleDES.block_size,
    )[:24]
    p1 = unpad(
        decrypt(
            symmetric_key_enc,
            algorithms.TripleDES(db_key),
            modes.CBC(b"J\xdd\xa2,y\xe8!\x05"),
        ),
        algorithms.TripleDES.block_size,
    )
    symmetric_key = unpad(
        decrypt(
            p1[:32][::-1], algorithms.TripleDES(db_key), modes.CBC(symmetric_key_IV)
        ),
        algorithms.TripleDES.block_size,
    )[4:]
    icloud_key = unpad(
        decrypt(
            icloud_key_enc,
            algorithms.TripleDES(symmetric_key),
            modes.CBC(icloud_key_IV),
        ),
        algorithms.TripleDES.block_size,
    )
    return icloud_key
