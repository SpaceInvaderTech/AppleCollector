#!/usr/bin/env python3

from argparse import ArgumentParser
from base64 import b64encode
from random import getrandbits
from helpers import get_public_key, int_to_bytes, sha256


parser = ArgumentParser()
parser.add_argument(
    "-n", "--nkeys", help="number of keys to generate", type=int, default=1
)
parser.add_argument("-p", "--prefix", help="prefix of the keyfiles")
parser.add_argument(
    "-y", "--yaml", help="yaml file where to write the list of generated keys"
)
parser.add_argument(
    "-v", "--verbose", help="print keys as they are generated", action="store_true"
)
args = parser.parse_args()

if args.yaml:
    yaml = open(args.yaml + ".yaml", "w")
    yaml.write("  keys:\n")

for i in range(args.nkeys):
    priv = getrandbits(224)
    adv = get_public_key(priv)

    priv_bytes = int_to_bytes(priv, 28)
    adv_bytes = int_to_bytes(adv, 28)

    priv_b64 = b64encode(priv_bytes).decode("ascii")
    adv_b64 = b64encode(adv_bytes).decode("ascii")
    s256_b64 = b64encode(sha256(adv_bytes)).decode("ascii")

    if args.verbose:
        print("%d)" % (i + 1))
        print("Private key: %s" % priv_b64)
        print("Advertisement key: %s" % adv_b64)
        print("Hashed adv key: %s" % s256_b64)

    if "/" in s256_b64[:7]:
        print("no key file written, there was a / in the b64 of the hashed pubkey :(")
    else:
        if args.prefix:
            fname = "%s_%s.keys" % (args.prefix, s256_b64[:7])
        else:
            fname = "%s.keys" % s256_b64[:7]

        with open(fname, "w") as f:
            f.write("Private key: %s\n" % priv_b64)
            f.write("Advertisement key: %s\n" % adv_b64)
            f.write("Hashed adv key: %s\n" % s256_b64)

        if args.yaml:
            yaml.write('    - "%s"\n' % adv_b64)
