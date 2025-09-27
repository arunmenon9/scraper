#!/usr/bin/env python3
"""
Scraper Daemon for Newegg
Database-driven scraper that periodically polls for pending work
"""

import os
import sys
import time
import json
import signal
from datetime import datetime
from typing import Dict, Any, Optional
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.database.database import DatabaseHandler
from core.scrapers.html_fetcher import SimpleNeweggFetcher
from core.scrapers.reviews_fetcher import NeweggReviewsFetcher
from config import settings

class ScraperDaemon:
    def __init__(self, db_path: str = None, raw_data_dir: str = None):
        # Use environment variable or default path
        if db_path is None:
            db_path = settings.DATABASE_PATH
        if raw_data_dir is None:
            raw_data_dir = settings.RAW_DATA_DIR
        # Use absolute path for database to avoid issues when changing working directories
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        self.db = DatabaseHandler(db_path)
        self.raw_data_dir = raw_data_dir
        self.running = False
        self.html_fetcher = None
        self.reviews_fetcher = None

        # Statistics
        self.stats = {
            "html_fetches_attempted": 0,
            "html_fetches_successful": 0,
            "review_fetches_attempted": 0,
            "review_fetches_successful": 0,
            "start_time": None,
            "last_activity": None
        }

        # Create output directories
        os.makedirs(self.raw_data_dir, exist_ok=True)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
        self.running = False

    def _create_session_directory(self, session_id: str) -> str:
        """Create directory for session data"""
        session_dir = os.path.join(self.raw_data_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        os.makedirs(os.path.join(session_dir, "html"), exist_ok=True)
        os.makedirs(os.path.join(session_dir, "api_responses"), exist_ok=True)
        return session_dir

    def fetch_html_for_session(self, session: Dict[str, Any]) -> bool:
        """Fetch HTML for a single session"""
        session_id = session["id"]
        product_url = session["product_url"]

        print(f"🔍 Fetching HTML for session {session_id}: {product_url}")

        try:
            # Create session directory
            session_dir = self._create_session_directory(session["session_id"])
            html_dir = os.path.join(session_dir, "html")

            # Initialize HTML fetcher if needed
            if not self.html_fetcher:
                self.html_fetcher = SimpleNeweggFetcher()

            # Change to HTML directory to save files there
            original_dir = os.getcwd()
            os.chdir(html_dir)

            try:
                success = self.html_fetcher.fetch_html(product_url)

                if success:
                    # Find the saved HTML file
                    html_files = [f for f in os.listdir('.') if f.endswith('.html')]
                    if html_files:
                        # Use the first successful HTML file
                        html_file = html_files[0]
                        file_location = os.path.join(html_dir, html_file)

                        self.db.update_html_fetch_status(session_id, 'completed', file_location)
                        print(f"✅ HTML fetch successful: {html_file}")

                        self.stats["html_fetches_successful"] += 1
                        return True
                    else:
                        error_msg = "No HTML files were saved"
                        self.db.update_html_fetch_status(session_id, 'failed', error_message=error_msg)
                        print(f"❌ HTML fetch failed: {error_msg}")
                        return False
                else:
                    error_msg = "HTML fetch returned False"
                    self.db.update_html_fetch_status(session_id, 'failed', error_message=error_msg)
                    print(f"❌ HTML fetch failed: {error_msg}")
                    return False

            finally:
                os.chdir(original_dir)

        except Exception as e:
            error_msg = f"Exception during HTML fetch: {str(e)}"
            self.db.update_html_fetch_status(session_id, 'failed', error_message=error_msg)
            print(f"❌ HTML fetch failed: {error_msg}")
            return False

    def fetch_reviews_for_session(self, session: Dict[str, Any]) -> bool:
        """Fetch reviews for a single session"""
        session_id = session["id"]
        product_url = session["product_url"]

        print(f"📊 Fetching reviews for session {session_id}: {product_url}")

        try:
            # Create session directory
            session_dir = self._create_session_directory(session["session_id"])
            api_dir = os.path.join(session_dir, "api_responses")

            # Get existing session if HTML fetcher was used
            existing_session = None
            if self.html_fetcher:
                existing_session = self.html_fetcher.get_session()

            # Initialize reviews fetcher
            self.reviews_fetcher = NeweggReviewsFetcher(existing_session=existing_session)

            # Fetch reviews (3 pages by default)
            reviews_data = self.reviews_fetcher.fetch_reviews(product_url, max_pages=3)

            if reviews_data and reviews_data.get("reviews"):
                # Save reviews data to API directory
                reviews_file = os.path.join(api_dir, "reviews_data.json")
                with open(reviews_file, 'w', encoding='utf-8') as f:
                    json.dump(reviews_data, f, indent=2, ensure_ascii=False)

                self.db.update_review_fetch_status(session_id, 'completed', reviews_file)

                reviews_count = len(reviews_data["reviews"])
                print(f"✅ Review fetch successful: {reviews_count} reviews")

                self.stats["review_fetches_successful"] += 1
                return True
            else:
                error_msg = "No reviews data returned from API"
                self.db.update_review_fetch_status(session_id, 'failed', error_message=error_msg)
                print(f"❌ Review fetch failed: {error_msg}")
                return False

        except Exception as e:
            error_msg = f"Exception during review fetch: {str(e)}"
            self.db.update_review_fetch_status(session_id, 'failed', error_message=error_msg)
            print(f"❌ Review fetch failed: {error_msg}")
            return False

    def process_html_queue(self, batch_size: int = 5) -> int:
        """Process pending HTML fetch requests"""
        pending_sessions = self.db.get_pending_html_fetch_sessions(limit=batch_size)

        if not pending_sessions:
            return 0

        print(f"\n🔍 Processing {len(pending_sessions)} HTML fetch requests...")
        successful = 0

        for session in pending_sessions:
            if not self.running:
                break

            self.stats["html_fetches_attempted"] += 1

            if self.fetch_html_for_session(session):
                successful += 1

            # Small delay between requests
            time.sleep(2)

        return successful

    def process_review_queue(self, batch_size: int = 5) -> int:
        """Process pending review fetch requests"""
        pending_sessions = self.db.get_pending_review_fetch_sessions(limit=batch_size)

        if not pending_sessions:
            return 0

        print(f"\n📊 Processing {len(pending_sessions)} review fetch requests...")
        successful = 0

        for session in pending_sessions:
            if not self.running:
                break

            self.stats["review_fetches_attempted"] += 1

            if self.fetch_reviews_for_session(session):
                successful += 1

            # Small delay between requests
            time.sleep(2)

        return successful

    def print_status(self):
        """Print current daemon status"""
        stats = self.db.get_session_statistics()

        print(f"\n📊 SCRAPER DAEMON STATUS")
        print("=" * 50)
        print(f"⏰ Running since: {self.stats['start_time']}")
        print(f"🔄 Last activity: {self.stats['last_activity']}")

        print(f"\n📈 SESSION STATS:")
        print(f"   Total sessions: {stats['total_sessions']}")
        print(f"   HTML pending: {stats['html_fetch_stats'].get('pending', 0)}")
        print(f"   Review pending: {stats['review_fetch_stats'].get('pending', 0)}")
        print(f"   Parsing pending: {stats['parsing_stats'].get('pending', 0)}")

        print(f"\n🎯 DAEMON PERFORMANCE:")
        print(f"   HTML fetches attempted: {self.stats['html_fetches_attempted']}")
        print(f"   HTML fetches successful: {self.stats['html_fetches_successful']}")
        print(f"   Review fetches attempted: {self.stats['review_fetches_attempted']}")
        print(f"   Review fetches successful: {self.stats['review_fetches_successful']}")

        if self.stats['html_fetches_attempted'] > 0:
            html_success_rate = (self.stats['html_fetches_successful'] / self.stats['html_fetches_attempted']) * 100
            print(f"   HTML success rate: {html_success_rate:.1f}%")

        if self.stats['review_fetches_attempted'] > 0:
            review_success_rate = (self.stats['review_fetches_successful'] / self.stats['review_fetches_attempted']) * 100
            print(f"   Review success rate: {review_success_rate:.1f}%")

    def run_daemon(self, poll_interval: int = 30, batch_size: int = 5, run_once: bool = False):
        """Run the scraper daemon"""
        print(f"🚀 NEWEGG SCRAPER DAEMON STARTING")
        print("=" * 50)
        print(f"📊 Poll interval: {poll_interval} seconds")
        print(f"📦 Batch size: {batch_size}")
        print(f"🔄 Run mode: {'One-time' if run_once else 'Continuous'}")
        print(f"📁 Data directory: {self.raw_data_dir}")
        print("Press Ctrl+C to stop")

        self.running = True
        self.stats["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cycle_count = 0

        try:
            while self.running:
                cycle_count += 1
                cycle_start = time.time()

                print(f"\n🔄 Cycle {cycle_count} - {datetime.now().strftime('%H:%M:%S')}")

                # Process HTML queue
                html_processed = self.process_html_queue(batch_size)

                # Process review queue
                review_processed = self.process_review_queue(batch_size)

                self.stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if html_processed > 0 or review_processed > 0:
                    print(f"✅ Cycle {cycle_count} completed: {html_processed} HTML, {review_processed} reviews")
                else:
                    print(f"💤 Cycle {cycle_count}: No pending work found")

                # Show status every 10 cycles or if work was done
                if cycle_count % 10 == 0 or html_processed > 0 or review_processed > 0:
                    self.print_status()

                # Exit if run_once mode
                if run_once:
                    break

                # Sleep until next poll
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, poll_interval - cycle_duration)

                if sleep_time > 0:
                    print(f"⏳ Sleeping for {sleep_time:.1f} seconds...")
                    for _ in range(int(sleep_time)):
                        if not self.running:
                            break
                        time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n🛑 Received shutdown signal...")

        finally:
            self.running = False
            print(f"\n🏁 SCRAPER DAEMON STOPPED")
            print(f"   Total runtime: {cycle_count} cycles")
            self.print_status()

def main():
    """Main CLI for scraper daemon"""
    print("🤖 NEWEGG SCRAPER DAEMON")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scraper_daemon.py start [--poll-interval=30] [--batch-size=5] [--data-dir=raw_data]")
        print("  python scraper_daemon.py run-once [--batch-size=5] [--data-dir=raw_data]")
        print("  python scraper_daemon.py status")
        print()
        print("Examples:")
        print("  python scraper_daemon.py start")
        print("  python scraper_daemon.py start --poll-interval=60 --batch-size=10")
        print("  python scraper_daemon.py run-once --batch-size=3")
        print("  python scraper_daemon.py status")
        return

    command = sys.argv[1]

    # Parse arguments
    poll_interval = 30
    batch_size = 5
    data_dir = None  # Use None to let ScraperDaemon use settings

    for arg in sys.argv[2:]:
        if arg.startswith("--poll-interval="):
            poll_interval = int(arg.split("=")[1])
        elif arg.startswith("--batch-size="):
            batch_size = int(arg.split("=")[1])
        elif arg.startswith("--data-dir="):
            data_dir = arg.split("=")[1]

    daemon = ScraperDaemon(raw_data_dir=data_dir)

    if command == "start":
        daemon.run_daemon(poll_interval=poll_interval, batch_size=batch_size, run_once=False)
    elif command == "run-once":
        daemon.run_daemon(poll_interval=poll_interval, batch_size=batch_size, run_once=True)
    elif command == "status":
        daemon.print_status()
    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: start, run-once, status")

if __name__ == "__main__":
    main()