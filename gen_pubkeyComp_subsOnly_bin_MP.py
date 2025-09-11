#!/usr/bin/env python3
"""
xpoint_pregen.py

Precompute "subtracted" public points for Keyhunt-style xpoint method,
using multiple cores to accelerate generation for large chunk counts.
Emits compressed pubkeys to a text file, and optionally raw X-coordinates to a binary file.

Usage:
  python xpoint_pregen.py \
    --pubkey 02abcdef... \
    --range "2**40" \
    --chunks 65536 \
    --output points.txt \
    [--bin-output subtracted_x.bin] \
    [--cores 4] [--block-size 100000]

Options:
  --cores (-c)      Number of parallel worker processes (default: 1)
  --block-size (-B) Number of i-steps per task block (default: 100000)
"""
import argparse
import sys
import time
import math
from multiprocessing import Pool
from contextlib import nullcontext
from ecdsa import ellipticcurve, curves

# Curve parameters
SECP     = curves.SECP256k1
CURVE    = SECP.curve
GEN      = SECP.generator
ORDER    = SECP.order
P_FIELD  = CURVE.p()
A        = CURVE.a()
B        = CURVE.b()

# Globals for worker processes (filled by initializer)
_global_P = None    # base point P
_global_Z = None    # stride Z
_global_bin = False


def parse_args():
    p = argparse.ArgumentParser(description="Pre-generate P - i·Z·G points with multiprocessing")
    p.add_argument('--pubkey', '-P', required=True,
                   help="Public key hex (compressed 02/03 or uncompressed 04)")
    p.add_argument('--range', '-X', required=True,
                   help="Overall search range X (Python expr, e.g. '2**40')")
    p.add_argument('--chunks', '-Y', type=int, required=True,
                   help="Number of chunks Y (must be even)")
    p.add_argument('--output', '-o', default='points.txt',
                   help="Output text filename")
    p.add_argument('--bin-output', '-b',
                   help="Optional binary output filename (raw 32‑byte X coords)")
    p.add_argument('--cores', '-c', type=int, default=1,
                   help="Number of parallel processes")
    p.add_argument('--block-size', '-B', type=int, default=100000,
                   help="Number of i per work block")
    return p.parse_args()


def hex_to_point(pub_hex: str):
    if pub_hex.startswith('04'):
        x = int(pub_hex[2:66], 16)
        y = int(pub_hex[66:], 16)
    elif pub_hex.startswith(('02','03')):
        prefix = int(pub_hex[:2], 16)
        x = int(pub_hex[2:], 16)
        alpha = (x*x*x + A*x + B) % P_FIELD
        y = pow(alpha, (P_FIELD+1)//4, P_FIELD)
        if (y % 2 == 0 and prefix == 0x03) or (y % 2 == 1 and prefix == 0x02):
            y = P_FIELD - y
    else:
        sys.exit("Error: pubkey must start with '02','03', or '04'.")
    return ellipticcurve.Point(CURVE, x, y, ORDER)


def point_to_compressed_hex(Pt: ellipticcurve.Point) -> str:
    prefix = '02' if Pt.y() % 2 == 0 else '03'
    return prefix + f"{Pt.x():064x}"


def init_worker(P, Z, bin_enabled):
    global _global_P, _global_Z, _global_bin
    _global_P = P
    _global_Z = Z
    _global_bin = bin_enabled


def worker_block(args):
    i_start, i_end = args
    P = _global_P
    Z = _global_Z
    bin_enabled = _global_bin
    text_lines = []
    bin_data = bytearray()
    for i in range(i_start, i_end):
        offset = i * Z
        k = offset % ORDER
        Q = k * GEN
        # P - i·Z·G (subtraction only)
        Q_neg = ellipticcurve.Point(CURVE, Q.x(), (-Q.y()) % P_FIELD, ORDER)
        P_sub = P + Q_neg
        hex_sub = point_to_compressed_hex(P_sub)
        text_lines.append(f"{hex_sub}  # -{offset}\n")
        if bin_enabled:
            bin_data += bytes.fromhex(hex_sub[2:])
    return text_lines, bin_data


def main():
    args = parse_args()
    P = hex_to_point(args.pubkey)
    X = eval(args.range, {}, {})
    Y = args.chunks
    if Y % 2 != 0:
        sys.exit("Error: chunks (Y) must be even.")
    Z = X // Y
    max_i = Y
    # Prepare output
    txt_f = open(args.output, 'w')
    bin_f = open(args.bin_output, 'wb') if args.bin_output else nullcontext()
    # Write header (zero offset)
    txt_f.write(f"{point_to_compressed_hex(P)}  # 0\n")
    if args.bin_output:
        bin_f.write(bytes.fromhex(point_to_compressed_hex(P)[2:]))  # include X0 in BIN too
    # Prepare blocks
    block_size = args.block_size
    blocks = [(i, min(i+block_size, max_i+1)) for i in range(1, max_i+1, block_size)]
    # Launch pool
    pool = Pool(processes=args.cores, initializer=init_worker, initargs=(P, Z, bool(args.bin_output)))
    try:
        for text_lines, bin_data in pool.imap(worker_block, blocks):
            txt_f.writelines(text_lines)
            if args.bin_output:
                bin_f.write(bin_data)
        pool.close()
        pool.join()
    finally:
        txt_f.close()
        if args.bin_output:
            bin_f.close()
    print(f"Generated {args.output} with {1 + max_i} points.")
    if args.bin_output:
        print(f"Wrote {1 + max_i} entries to {args.bin_output}.")

if __name__ == "__main__":
    main()