"""Shared Anthropic client setup.

Loads ANTHROPIC_API_KEY from .env (see .env.example) and exposes a single
client instance plus the default model name (Haiku, per docs/spec.md).
"""

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
