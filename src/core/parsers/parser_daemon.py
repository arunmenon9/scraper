#!/usr/bin/env python3
"""
Parser Daemon for Newegg
Database-driven parser that processes completed scraping sessions
"""

import os
import sys
import time
import json
import signal
from datetime import datetime
from typing import Dict, Any, List, Optional
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.database.database import DatabaseHandler
from core.parsers.newegg_parser import NeweggParser
from config import settings
from dataclasses import asdict

class ParserDaemon:
    def __init__(self, db_path: str = None):
        # Use environment variable or default path
        if db_path is None:
            db_path = settings.DATABASE_PATH
        # Use absolute path for database to avoid issues when changing working directories
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        self.db = DatabaseHandler(db_path)
        self.parser = NeweggParser(enable_database=True)
        self.running = False

        # Statistics
        self.stats = {
            "parsing_attempts": 0,
            "parsing_successful": 0,
            "products_processed": 0,
            "reviews_processed": 0,
            "start_time": None,
            "last_activity": None
        }

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
        self.running = False

    def parse_single_session(self, session: Dict[str, Any]) -> bool:
        """Parse a single completed session"""
        session_id = session["id"]
        product_url = session["product_url"]
        html_file = session["html_file_location"]
        review_file = session["review_data_location"]

        # Extract product ID from URL first
        url_product_id = None
        if product_url:
            import re
            url_match = re.search(r'/p/([A-Z0-9\-]+)', product_url)
            if url_match:
                url_product_id = url_match.group(1)
                print(f"🔍 Extracted product ID from URL: {url_product_id}")

        print(f"🔄 Parsing session {session_id}: {product_url}")

        try:
            # Parse HTML for product information
            product_info = None
            if html_file and os.path.exists(html_file):
                product_info = self.parse_html_file(html_file, url_product_id)

            # Parse reviews data
            reviews = []
            review_fetch_failed = False
            if review_file and os.path.exists(review_file):
                reviews = self.parse_reviews_file(review_file)
            else:
                # Review fetch failed or no review file available
                review_fetch_failed = True
                if review_file is None:
                    print(f"⚠️ No review data available (review fetch failed - no file location)")
                else:
                    print(f"⚠️ No review data available (review fetch failed - file not found: {review_file})")

            # Update database with parsed data
            # Process even if only product info is available (when review fetch failed)
            if product_info:
                # Insert/update product with session link
                product_id = self.db.insert_or_update_product(asdict(product_info), product_url, session["session_id"])
                self.stats["products_processed"] += 1

                # Insert reviews (if any were successfully parsed)
                if reviews and product_id:
                    inserted_count = self.db.insert_reviews(product_id, [asdict(r) for r in reviews])
                    self.stats["reviews_processed"] += inserted_count

                # Update parsing status
                self.db.update_parsing_status(session_id, 'completed')

                if review_fetch_failed:
                    print(f"✅ Parsing successful: product updated (review fetch had failed)")
                else:
                    print(f"✅ Parsing successful: {len(reviews)} reviews, product updated")
                self.stats["parsing_successful"] += 1
                return True
            else:
                error_msg = "No product data could be parsed from HTML file"
                self.db.update_parsing_status(session_id, 'failed', error_msg)
                print(f"❌ Parsing failed: {error_msg}")

        except Exception as e:
            error_msg = f"Exception during parsing: {str(e)}"
            self.db.update_parsing_status(session_id, 'failed', error_msg)
            print(f"❌ Parsing failed: {error_msg}")

        return False

    def parse_html_file(self, html_file: str, url_product_id: str = None) -> Optional[Any]:
        """Parse HTML file for product information"""
        try:
            from bs4 import BeautifulSoup
            from core.parsers.newegg_parser import ProductInfo
            import re

            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract title from meta tag
            title = "N/A"
            title_elem = soup.find('meta', {'property': 'og:title'})
            if title_elem:
                title = title_elem.get('content', '').replace(' - Newegg.com', '').strip()

            # Extract brand from brand store link
            brand = "N/A"
            brand_link = soup.find('a', href=lambda x: x and 'BrandStore' in x)
            if brand_link:
                brand = brand_link.get('title', '').replace('Visit ', '').strip()

            # Extract price from buy box
            price = "N/A"
            price_elem = soup.find('div', class_='price-current')
            if price_elem:
                price = price_elem.get_text(strip=True)

            # Extract rating and reviews count
            rating = "N/A"
            reviews_count = "N/A"

            # Look for the product-reviews section
            product_reviews = soup.find(class_='product-reviews')
            if product_reviews:
                # Extract rating
                for elem in product_reviews.find_all(attrs={'title': re.compile(r'\d+(?:\.\d+)? out of', re.IGNORECASE)}):
                    title_attr = elem.get('title', '')
                    rating_match = re.search(r'(\d+(?:\.\d+)?) out of 5 eggs', title_attr, re.IGNORECASE)
                    if rating_match:
                        rating = rating_match.group(1)
                        break

                # Extract review count
                for elem in product_reviews.find_all(['span', 'a']):
                    text = elem.get_text(strip=True)
                    if '(' in text and ')' in text:
                        match = re.search(r'\((\d+)\)', text)
                        if match:
                            reviews_count = match.group(1)  # Extract just the number, not the parentheses
                            break

            # Extract description from meta tag
            description = "N/A"
            desc_elem = soup.find('meta', {'name': 'description'})
            if desc_elem:
                description = desc_elem.get('content', '').replace('Buy ', '').strip()
                if len(description) > 200:
                    description = description[:200] + "..."

            # Use URL product ID as primary source for item number
            newegg_item_number = ""
            item_number = ""

            if url_product_id:
                # Always use URL product ID as the authoritative source
                newegg_item_number = url_product_id
                item_number = url_product_id
                print(f"✅ Using URL product ID as item number: {url_product_id}")
            else:
                # Fallback to HTML parsing only if URL extraction failed
                print(f"⚠️ No URL product ID found, falling back to HTML parsing")
                item_patterns = [
                    r'N82E16\d+',
                    r'"ItemNumber"\s*:\s*"([^"]+)"',
                    r'"NeweggItemNumber"\s*:\s*"([^"]+)"',
                    r'/p/([A-Z0-9\-]+)',  # Extract from URL path like /p/14S-0041-002X9
                    r'data-product-item="([^"]+)"',  # HTML data attributes
                    r'itemNumber["\']?\s*[:=]\s*["\']?([A-Z0-9\-]+)',  # Various JS patterns
                    r'product[_\-]?id["\']?\s*[:=]\s*["\']?([A-Z0-9\-]+)'  # Product ID patterns
                ]

                for i, pattern in enumerate(item_patterns, 1):
                    matches = re.findall(pattern, html_content)
                    print(f"🔍 Pattern {i} ({pattern[:20]}...): {len(matches)} matches")
                    if matches:
                        newegg_item_number = matches[0]
                        print(f"✅ Found item number using pattern {i}: {newegg_item_number}")
                        if newegg_item_number.startswith('N82E16'):
                            # Format N82E16 item numbers
                            number_match = re.search(r'N82E16(\d+)', newegg_item_number)
                            if number_match:
                                full_number = number_match.group(1)
                                if len(full_number) >= 8 and full_number.startswith('8'):
                                    clean_number = full_number[1:]
                                    item_number = f"{clean_number[:2]}-{clean_number[2:5]}-{clean_number[5:]}"
                                else:
                                    item_number = full_number
                        else:
                            # Handle non-N82E16 item numbers (like 3C6-0064-00002, 1A9-0005-006V3)
                            item_number = newegg_item_number
                        break

            product = ProductInfo(
                title=title,
                brand=brand,
                price=price,
                rating=rating,
                reviews_count=reviews_count,
                description=description,
                newegg_item_number=newegg_item_number,
                item_number=item_number
            )

            print(f"🔍 Extracted product info:")
            print(f"   Title: {title}")
            print(f"   Newegg Item Number: {newegg_item_number}")
            print(f"   Item Number: {item_number}")
            print(f"   Brand: {brand}")

            # Check if we have essential data
            if not newegg_item_number:
                print(f"❌ CRITICAL: No newegg_item_number extracted - product will not be saved!")
                print(f"   URL product ID was: {url_product_id}")
                return None

            if not title:
                print(f"⚠️ WARNING: No title extracted - this may cause issues")

            return product

        except Exception as e:
            print(f"⚠️ Error parsing HTML file {html_file}: {e}")
            return None

    def parse_reviews_file(self, review_file: str) -> List[Any]:
        """Parse reviews from JSON file"""
        try:
            from core.parsers.newegg_parser import Review

            with open(review_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            reviews = []

            # Handle different JSON structures
            reviews_data = None

            if 'reviews' in data:
                # Direct reviews list
                reviews_data = data['reviews']
            elif isinstance(data, list):
                # Direct list of reviews
                reviews_data = data
            else:
                # Try to find reviews in nested structure
                for key, value in data.items():
                    if isinstance(value, list) and value and 'reviewer_name' in str(value[0]):
                        reviews_data = value
                        break

            if reviews_data:
                for review_data in reviews_data:
                    # Convert dict to Review object
                    review = Review(
                        reviewer_name=review_data.get('reviewer_name', 'Anonymous'),
                        rating=str(review_data.get('rating', 0)),
                        review_title=review_data.get('review_title', ''),
                        review_body=review_data.get('review_body', ''),
                        date=review_data.get('date', ''),
                        verified_buyer=review_data.get('verified_buyer', False),
                        helpful_count=review_data.get('helpful_count'),
                        pros=review_data.get('pros'),
                        cons=review_data.get('cons'),
                        purchase_mark=review_data.get('purchase_mark'),
                        total_voting=review_data.get('total_voting'),
                        vendor_reply=review_data.get('vendor_reply'),
                        item_number=review_data.get('item_number'),
                        brand=review_data.get('brand'),
                        product_description=review_data.get('product_description')
                    )
                    reviews.append(review)

            return reviews

        except Exception as e:
            print(f"⚠️ Error parsing review file {review_file}: {e}")
            return []

    def process_parsing_queue(self, batch_size: int = 5) -> int:
        """Process sessions ready for parsing"""
        ready_sessions = self.db.get_ready_for_parsing_sessions(limit=batch_size)

        if not ready_sessions:
            return 0

        print(f"\n🔄 Processing {len(ready_sessions)} parsing requests...")
        successful = 0

        for session in ready_sessions:
            if not self.running:
                break

            self.stats["parsing_attempts"] += 1

            if self.parse_single_session(session):
                successful += 1

            # Small delay between sessions
            time.sleep(1)

        return successful

    def print_status(self):
        """Print current daemon status"""
        stats = self.db.get_session_statistics()

        print(f"\n📊 PARSER DAEMON STATUS")
        print("=" * 50)
        print(f"⏰ Running since: {self.stats['start_time']}")
        print(f"🔄 Last activity: {self.stats['last_activity']}")

        print(f"\n📈 SESSION STATS:")
        print(f"   Total sessions: {stats['total_sessions']}")
        print(f"   Ready for parsing: {stats['parsing_stats'].get('pending', 0)}")
        print(f"   Parsing completed: {stats['parsing_stats'].get('completed', 0)}")
        print(f"   Parsing failed: {stats['parsing_stats'].get('failed', 0)}")

        print(f"\n🎯 DAEMON PERFORMANCE:")
        print(f"   Parsing attempts: {self.stats['parsing_attempts']}")
        print(f"   Parsing successful: {self.stats['parsing_successful']}")
        print(f"   Products processed: {self.stats['products_processed']}")
        print(f"   Reviews processed: {self.stats['reviews_processed']}")

        if self.stats['parsing_attempts'] > 0:
            success_rate = (self.stats['parsing_successful'] / self.stats['parsing_attempts']) * 100
            print(f"   Success rate: {success_rate:.1f}%")

    def run_daemon(self, poll_interval: int = 30, batch_size: int = 5, run_once: bool = False):
        """Run the parser daemon"""
        print(f"🤖 NEWEGG PARSER DAEMON STARTING")
        print("=" * 50)
        print(f"📊 Poll interval: {poll_interval} seconds")
        print(f"📦 Batch size: {batch_size}")
        print(f"🔄 Run mode: {'One-time' if run_once else 'Continuous'}")
        print("Press Ctrl+C to stop")

        self.running = True
        self.stats["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cycle_count = 0

        try:
            while self.running:
                cycle_count += 1
                cycle_start = time.time()

                print(f"\n🔄 Cycle {cycle_count} - {datetime.now().strftime('%H:%M:%S')}")

                # Process parsing queue
                parsed = self.process_parsing_queue(batch_size)

                self.stats["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if parsed > 0:
                    print(f"✅ Cycle {cycle_count} completed: {parsed} sessions parsed")
                else:
                    print(f"💤 Cycle {cycle_count}: No sessions ready for parsing")

                # Show status every 10 cycles or if work was done
                if cycle_count % 10 == 0 or parsed > 0:
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
            print(f"\n🏁 PARSER DAEMON STOPPED")
            print(f"   Total runtime: {cycle_count} cycles")
            self.print_status()

def main():
    """Main CLI for parser daemon"""
    print("🤖 NEWEGG PARSER DAEMON")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python parser_daemon.py start [--poll-interval=30] [--batch-size=5]")
        print("  python parser_daemon.py run-once [--batch-size=5]")
        print("  python parser_daemon.py status")
        print()
        print("Examples:")
        print("  python parser_daemon.py start")
        print("  python parser_daemon.py start --poll-interval=60 --batch-size=10")
        print("  python parser_daemon.py run-once --batch-size=3")
        print("  python parser_daemon.py status")
        return

    command = sys.argv[1]

    # Parse arguments
    poll_interval = 30
    batch_size = 5

    for arg in sys.argv[2:]:
        if arg.startswith("--poll-interval="):
            poll_interval = int(arg.split("=")[1])
        elif arg.startswith("--batch-size="):
            batch_size = int(arg.split("=")[1])

    daemon = ParserDaemon()

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