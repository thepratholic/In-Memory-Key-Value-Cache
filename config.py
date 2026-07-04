"""
Config
======
Saare environment variables ek hi jagah — taaki kahin bhi
hardcoded values na hon, aur settings dhundhne ke liye
poori codebase na chhaanni pade.
"""

import os

NUM_SHARDS          = int(os.getenv("NUM_SHARDS", "16"))        # kitne shards — power of 2
MAX_ITEMS_PER_SHARD = int(os.getenv("MAX_SHARD_SIZE", "700_000")) # ek shard mein max keys
MAX_KEY_VALUE_SIZE  = int(os.getenv("MAX_KV_SIZE", "256"))       # key/value max length
PORT                = int(os.getenv("PORT", "7171"))
HOST                = os.getenv("HOST", "127.0.0.1")