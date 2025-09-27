#!/usr/bin/env python3
"""
Main entry point for Newegg Scraper
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.orchestrator import main

if __name__ == "__main__":
    main()