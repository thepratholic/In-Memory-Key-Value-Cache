"""
Models
======
HTTP request bodies aur unki validation — server.py se alag,
kyunki yeh "data shape" ki concern hai, routing logic ki nahi.
"""

from pydantic import BaseModel, field_validator

from config import MAX_KEY_VALUE_SIZE


class PutRequest(BaseModel):
    """PUT endpoint ke liye incoming JSON — Pydantic automatically validate karta hai."""
    key: str
    value: str

    @field_validator("key", "value")
    @classmethod
    def check_size(cls, v: str) -> str:
        if len(v) > MAX_KEY_VALUE_SIZE:
            raise ValueError(f"Must be <= {MAX_KEY_VALUE_SIZE} characters")
        return v

    @field_validator("key")
    @classmethod
    def check_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Key cannot be empty")
        return v