#!/usr/bin/env python3
"""
Main Orchestrator for Newegg Scraper
Coordinates CSV processing, scraping, and parsing workflows
"""

import sys
import os
import subprocess
import time
import signal
from typing import Dict, Any, List
from core.database.database import DatabaseHandler
from utils.csv_processor import CSVProcessor
from config import settings

class ScraperOrchestrator:
    def __init__(self, db_path: str = None):
        # Use settings database path if not provided
        if db_path is None:
            db_path = settings.DATABASE_PATH
        # Use absolute path for database consistency
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        self.db_path = db_path
        self.db = DatabaseHandler(db_path)
        self.csv_processor = CSVProcessor(db_path)

        # Process handles
        self.scraper_process = None
        self.parser_process = None
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}. Shutting down services...")
        self.running = False
        self.stop_services()

    def stop_services(self):
        """Stop all running services"""
        if self.scraper_process:
            print("🛑 Stopping scraper daemon...")
            self.scraper_process.terminate()
            try:
                self.scraper_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.scraper_process.kill()
            self.scraper_process = None

        if self.parser_process:
            print("🛑 Stopping parser daemon...")
            self.parser_process.terminate()
            try:
                self.parser_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.parser_process.kill()
            self.parser_process = None

    def process_csv_file(self, csv_file: str, dry_run: bool = False) -> bool:
        """Process CSV file and populate database"""
        print(f"📄 PROCESSING CSV FILE: {csv_file}")
        print("=" * 50)

        if not os.path.exists(csv_file):
            print(f"❌ CSV file not found: {csv_file}")
            return False

        result = self.csv_processor.process_csv_file(csv_file)

        if result["success"]:
            if not dry_run:
                print(f"✅ CSV processed successfully!")
                print(f"   Sessions created: {result['sessions_created']}")
                return True
            else:
                print(f"✅ CSV validation passed (dry run)")
                return True
        else:
            print(f"❌ CSV processing failed: {result['error']}")
            return False

    def start_scraper_daemon(self, poll_interval: int = 30, batch_size: int = 5) -> bool:
        """Start the scraper daemon"""
        print(f"🚀 Starting scraper daemon...")

        cmd = [
            sys.executable, os.path.join(os.path.dirname(__file__), "..", "scraper.py"), "start",
            f"--poll-interval={poll_interval}",
            f"--batch-size={batch_size}"
        ]

        try:
            # Start with visible output so we can see what's happening
            self.scraper_process = subprocess.Popen(
                cmd,
                stdout=None,  # Let output go to console
                stderr=None,  # Let errors go to console
                universal_newlines=True
            )
            print(f"✅ Scraper daemon started (PID: {self.scraper_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Failed to start scraper daemon: {e}")
            return False

    def start_parser_daemon(self, poll_interval: int = 30, batch_size: int = 5) -> bool:
        """Start the parser daemon"""
        print(f"🤖 Starting parser daemon...")

        cmd = [
            sys.executable, os.path.join(os.path.dirname(__file__), "..", "parser.py"), "start",
            f"--poll-interval={poll_interval}",
            f"--batch-size={batch_size}"
        ]

        try:
            # Start with visible output so we can see what's happening
            self.parser_process = subprocess.Popen(
                cmd,
                stdout=None,  # Let output go to console
                stderr=None,  # Let errors go to console
                universal_newlines=True
            )
            print(f"✅ Parser daemon started (PID: {self.parser_process.pid})")
            return True
        except Exception as e:
            print(f"❌ Failed to start parser daemon: {e}")
            return False

    def monitor_services(self):
        """Monitor running services and show status"""
        print(f"\n📊 SERVICE MONITORING")
        print("=" * 50)

        while self.running:
            # Check service status
            scraper_running = self.scraper_process and self.scraper_process.poll() is None
            parser_running = self.parser_process and self.parser_process.poll() is None

            print(f"\n⏰ {time.strftime('%H:%M:%S')} - Service Status:")
            print(f"   🚀 Scraper: {'✅ Running' if scraper_running else '❌ Stopped'}")
            print(f"   🤖 Parser: {'✅ Running' if parser_running else '❌ Stopped'}")

            # Show database statistics
            try:
                stats = self.db.get_session_statistics()
                print(f"\n📈 Database Status:")
                print(f"   Total sessions: {stats['total_sessions']}")
                print(f"   HTML pending: {stats['html_fetch_stats'].get('pending', 0)}")
                print(f"   Reviews pending: {stats['review_fetch_stats'].get('pending', 0)}")
                print(f"   Parsing pending: {stats['parsing_stats'].get('pending', 0)}")
                print(f"   Completed: {stats['parsing_stats'].get('completed', 0)}")
                print(f"   Failed: {stats['html_failed_count'] + stats['review_failed_count']}")
            except Exception as e:
                print(f"⚠️ Could not get database stats: {e}")

            # Restart failed services
            if not scraper_running and self.scraper_process:
                print(f"⚠️ Scraper daemon stopped. Attempting restart...")
                self.start_scraper_daemon()

            if not parser_running and self.parser_process:
                print(f"⚠️ Parser daemon stopped. Attempting restart...")
                self.start_parser_daemon()

            # Wait before next check
            for _ in range(60):  # 60 seconds
                if not self.running:
                    break
                time.sleep(1)

    def run_complete_workflow(
        self,
        csv_file: str,
        scraper_poll_interval: int = 30,
        parser_poll_interval: int = 30,
        batch_size: int = 5,
        monitor: bool = True
    ):
        """Run the complete workflow"""
        print(f"🎯 NEWEGG SCRAPER COMPLETE WORKFLOW")
        print("=" * 60)
        print(f"📄 CSV File: {csv_file}")
        print(f"⏱️ Scraper Poll: {scraper_poll_interval}s")
        print(f"⏱️ Parser Poll: {parser_poll_interval}s")
        print(f"📦 Batch Size: {batch_size}")
        print(f"👁️ Monitor: {monitor}")

        self.running = True

        try:
            # Step 1: Process CSV file
            if not self.process_csv_file(csv_file):
                print("❌ CSV processing failed. Aborting workflow.")
                return

            # Step 2: Start scraper daemon
            if not self.start_scraper_daemon(scraper_poll_interval, batch_size):
                print("❌ Could not start scraper daemon. Aborting workflow.")
                return

            # Step 3: Start parser daemon
            if not self.start_parser_daemon(parser_poll_interval, batch_size):
                print("❌ Could not start parser daemon. Aborting workflow.")
                self.stop_services()
                return

            print(f"\n🎉 All services started successfully!")
            print(f"   Scraper PID: {self.scraper_process.pid}")
            print(f"   Parser PID: {self.parser_process.pid}")

            if monitor:
                print(f"\n👁️ Starting monitoring (Press Ctrl+C to stop)...")
                self.monitor_services()
            else:
                print(f"\n✅ Services are running in background")
                print(f"   Use 'python orchestrator.py status' to check progress")

        except KeyboardInterrupt:
            print(f"\n🛑 Received shutdown signal...")
        finally:
            self.running = False
            self.stop_services()
            print(f"\n🏁 Workflow completed")

    def show_status(self):
        """Show current status of all components"""
        print(f"📊 NEWEGG SCRAPER STATUS")
        print("=" * 50)

        # Database statistics
        try:
            stats = self.db.get_session_statistics()
            total = stats['total_sessions']

            print(f"📈 DATABASE STATISTICS:")
            print(f"   Total sessions: {total}")

            if total > 0:
                html_completed = stats['html_fetch_stats'].get('completed', 0)
                review_completed = stats['review_fetch_stats'].get('completed', 0)
                parsing_completed = stats['parsing_stats'].get('completed', 0)

                print(f"\n🔍 HTML FETCH:")
                for status, count in stats['html_fetch_stats'].items():
                    pct = (count / total) * 100 if total > 0 else 0
                    print(f"   {status}: {count} ({pct:.1f}%)")

                print(f"\n📊 REVIEW FETCH:")
                for status, count in stats['review_fetch_stats'].items():
                    pct = (count / total) * 100 if total > 0 else 0
                    print(f"   {status}: {count} ({pct:.1f}%)")

                print(f"\n🔄 PARSING:")
                for status, count in stats['parsing_stats'].items():
                    pct = (count / total) * 100 if total > 0 else 0
                    print(f"   {status}: {count} ({pct:.1f}%)")

                print(f"\n❌ FAILURES:")
                print(f"   HTML failures: {stats['html_failed_count']}")
                print(f"   Review failures: {stats['review_failed_count']}")

                print(f"\n📈 OVERALL PROGRESS:")
                overall_pct = (parsing_completed / total) * 100
                print(f"   Completion rate: {overall_pct:.1f}% ({parsing_completed}/{total})")

        except Exception as e:
            print(f"❌ Could not get database statistics: {e}")

def main():
    """Main CLI for orchestrator"""
    print("🎯 NEWEGG SCRAPER ORCHESTRATOR")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python orchestrator.py run <csv_file> [--scraper-poll=30] [--parser-poll=30] [--batch-size=5] [--no-monitor]")
        print("  python orchestrator.py process-csv <csv_file> [--dry-run]")
        print("  python orchestrator.py start-scraper [--poll-interval=30] [--batch-size=5]")
        print("  python orchestrator.py start-parser [--poll-interval=30] [--batch-size=5]")
        print("  python orchestrator.py status")
        print("  python orchestrator.py stop")
        print()
        print("Examples:")
        print("  python orchestrator.py run urls.csv")
        print("  python orchestrator.py run urls.csv --scraper-poll=60 --batch-size=10")
        print("  python orchestrator.py process-csv urls.csv --dry-run")
        print("  python orchestrator.py status")
        return

    command = sys.argv[1]
    orchestrator = ScraperOrchestrator()

    if command == "run":
        if len(sys.argv) < 3:
            print("❌ CSV file required for run command")
            return

        csv_file = sys.argv[2]
        scraper_poll = 30
        parser_poll = 30
        batch_size = 5
        monitor = True

        # Parse arguments
        for arg in sys.argv[3:]:
            if arg.startswith("--scraper-poll="):
                scraper_poll = int(arg.split("=")[1])
            elif arg.startswith("--parser-poll="):
                parser_poll = int(arg.split("=")[1])
            elif arg.startswith("--batch-size="):
                batch_size = int(arg.split("=")[1])
            elif arg == "--no-monitor":
                monitor = False

        orchestrator.run_complete_workflow(
            csv_file, scraper_poll, parser_poll, batch_size, monitor
        )

    elif command == "process-csv":
        if len(sys.argv) < 3:
            print("❌ CSV file required for process-csv command")
            return

        csv_file = sys.argv[2]
        dry_run = "--dry-run" in sys.argv
        orchestrator.process_csv_file(csv_file, dry_run)

    elif command == "start-scraper":
        poll_interval = 30
        batch_size = 5

        for arg in sys.argv[2:]:
            if arg.startswith("--poll-interval="):
                poll_interval = int(arg.split("=")[1])
            elif arg.startswith("--batch-size="):
                batch_size = int(arg.split("=")[1])

        orchestrator.start_scraper_daemon(poll_interval, batch_size)

    elif command == "start-parser":
        poll_interval = 30
        batch_size = 5

        for arg in sys.argv[2:]:
            if arg.startswith("--poll-interval="):
                poll_interval = int(arg.split("=")[1])
            elif arg.startswith("--batch-size="):
                batch_size = int(arg.split("=")[1])

        orchestrator.start_parser_daemon(poll_interval, batch_size)

    elif command == "status":
        orchestrator.show_status()

    elif command == "stop":
        orchestrator.stop_services()
        print("✅ All services stopped")

    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: run, process-csv, start-scraper, start-parser, status, stop")

if __name__ == "__main__":
    main()