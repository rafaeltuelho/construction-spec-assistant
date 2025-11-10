#!/usr/bin/env python3
"""
Test script to verify .env file loading from different directories.
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.config import ENV_FILE_PATH, Settings

print("=" * 80)
print("Environment File Loading Test")
print("=" * 80)
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {Path(__file__).parent}")
print(f"Expected .env path: {ENV_FILE_PATH}")
print(f".env file exists: {ENV_FILE_PATH.exists()}")
print()

# Load settings
settings = Settings()

print("=" * 80)
print("Loaded Settings")
print("=" * 80)
print(f"TAVILY_SEARCH_ENABLED: {settings.tavily_search_enabled}")
print(f"TAVILY_API_KEY: {'***' + settings.tavily_api_key[-10:] if settings.tavily_api_key else 'Not set'}")
print(f"LLM_PROVIDER: {settings.llm_provider}")
print(f"MONGODB_URL: {settings.mongodb_url}")
print(f"QDRANT_HOST: {settings.qdrant_host}")
print(f"QDRANT_PORT: {settings.qdrant_port}")
print()

if settings.tavily_search_enabled and settings.tavily_api_key:
    print("✅ SUCCESS: Tavily is enabled and API key is loaded!")
else:
    print("❌ ISSUE: Tavily is not properly configured")
    print(f"   - TAVILY_SEARCH_ENABLED: {settings.tavily_search_enabled}")
    print(f"   - TAVILY_API_KEY: {'Set' if settings.tavily_api_key else 'Not set'}")

print("=" * 80)

