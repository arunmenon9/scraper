#!/usr/bin/env python3
"""
Web application entry point for Newegg Scraper
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.web.web_app import app
from src.config import settings

if __name__ == "__main__":
    app.run(
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        debug=settings.WEB_DEBUG
    )