"""
cache package
=============
Exposes ShardedCache as the single public entry point, taaki
baaki codebase ko internal files (shard.py, rwlock.py, hashing.py)
ke baare mein jaanna na pade.

Usage:
    from cache import ShardedCache
"""

from cache.sharded_cache import ShardedCache

__all__ = ["ShardedCache"]