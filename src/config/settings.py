"""
Configuration settings for Newegg Scraper
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Database configuration
DATABASE_PATH = Path(os.environ.get('DATABASE_PATH', BASE_DIR / 'data' / 'newegg_scraper.db'))

# Data directories
RAW_DATA_DIR = Path(os.environ.get('RAW_DATA_DIR', BASE_DIR / 'data' / 'raw_data'))
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', BASE_DIR / 'data' / 'uploads'))
LOGS_DIR = Path(os.environ.get('LOGS_DIR', BASE_DIR / 'logs'))

# Scraping configuration
DEFAULT_POLL_INTERVAL = int(os.environ.get('POLL_INTERVAL', '30'))
DEFAULT_BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '5'))
MAX_REVIEW_PAGES = int(os.environ.get('MAX_REVIEW_PAGES', '3'))

# Web interface configuration
WEB_HOST = os.environ.get('WEB_HOST', '0.0.0.0')
WEB_PORT = int(os.environ.get('WEB_PORT', '8000'))
WEB_DEBUG = os.environ.get('WEB_DEBUG', 'False').lower() == 'true'

# Rate limiting
REQUEST_DELAY = float(os.environ.get('REQUEST_DELAY', '2.0'))
RETRY_ATTEMPTS = int(os.environ.get('RETRY_ATTEMPTS', '3'))

# Create required directories
def ensure_directories():
    """Ensure all required directories exist"""
    for directory in [RAW_DATA_DIR, UPLOAD_DIR, LOGS_DIR, DATABASE_PATH.parent]:
        Path(directory).mkdir(parents=True, exist_ok=True)

# Initialize directories when module is imported
ensure_directories()