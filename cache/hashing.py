"""
DJB2 Hash
=========
Ek fast string hashing algorithm. Daniel J. Bernstein ne
banaya tha, isliye DJB2.

Kaam kaise karta hai:
  h = 5381  (magic seed — experimentally chosen, good distribution)
  har character ke liye:
      h = h * 33 + char_code
      (h << 5) + h  yahi h*33 hai, but bitwise shift se faster

Result: same string -> hamesha same number (deterministic)
Alag strings -> mostly alag numbers (good distribution)

& 0xFFFF_FFFF_FFFF_FFFF -> 64-bit mein rakhta hai (overflow nahi)
"""


def djb2_hash(s: str) -> int:
    h = 5381
    for ch in s.encode():
        h = ((h << 5) + h + ch) & 0xFFFF_FFFF_FFFF_FFFF
    return h