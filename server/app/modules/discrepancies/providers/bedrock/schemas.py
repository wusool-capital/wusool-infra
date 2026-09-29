"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.
"""

from pydantic import BaseModel


class PhrasedMessage(BaseModel):
    message: str
