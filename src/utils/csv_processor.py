#!/usr/bin/env python3
"""
CSV Processor for Newegg Scraper
Handles CSV input and populates the scraping_sessions table
"""

import sys
import os
import csv
from datetime import datetime
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.database.database import DatabaseHandler
from config import settings

class CSVProcessor:
    def __init__(self, db_path: str = None):
        # Use environment variable or default path
        if db_path is None:
            db_path = settings.DATABASE_PATH
        # Use absolute path for database consistency
        if not os.path.isabs(db_path):
            db_path = os.path.abspath(db_path)
        self.db = DatabaseHandler(db_path)

    def validate_csv_format(self, csv_file: str) -> Dict[str, Any]:
        """Validate CSV file format and content"""
        if not os.path.exists(csv_file):
            return {"valid": False, "error": f"File not found: {csv_file}"}

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                # Check if file is empty
                if os.path.getsize(csv_file) == 0:
                    return {"valid": False, "error": "CSV file is empty"}

                reader = csv.DictReader(f)
                headers = reader.fieldnames

                if not headers:
                    return {"valid": False, "error": "CSV file has no headers"}

                # Check required columns
                required_columns = ['url']
                missing_columns = [col for col in required_columns if col not in headers]

                if missing_columns:
                    return {
                        "valid": False,
                        "error": f"Missing required columns: {missing_columns}. Required: {required_columns}"
                    }

                # Count valid URLs
                valid_urls = 0
                invalid_urls = []
                row_count = 0

                for row_num, row in enumerate(reader, start=2):  # Start from 2 (header is row 1)
                    row_count += 1
                    url = row.get('url', '').strip()

                    if not url:
                        invalid_urls.append(f"Row {row_num}: Empty URL")
                        continue

                    if not (url.startswith('http://') or url.startswith('https://')):
                        invalid_urls.append(f"Row {row_num}: Invalid URL format: {url}")
                        continue

                    if 'newegg.com' not in url.lower():
                        invalid_urls.append(f"Row {row_num}: Not a Newegg URL: {url}")
                        continue

                    valid_urls += 1

                return {
                    "valid": True,
                    "total_rows": row_count,
                    "valid_urls": valid_urls,
                    "invalid_urls": invalid_urls[:10],  # Show first 10 invalid URLs
                    "invalid_count": len(invalid_urls),
                    "headers": headers
                }

        except Exception as e:
            return {"valid": False, "error": f"Error reading CSV file: {str(e)}"}

    def process_csv_file(self, csv_file: str) -> Dict[str, Any]:
        """Process CSV file and create scraping sessions"""
        print(f"🔍 Processing CSV file: {csv_file}")

        # Validate CSV first
        validation = self.validate_csv_format(csv_file)

        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"],
                "sessions_created": 0
            }

        print(f"✅ CSV validation passed:")
        print(f"   Total rows: {validation['total_rows']}")
        print(f"   Valid URLs: {validation['valid_urls']}")
        print(f"   Invalid URLs: {validation['invalid_count']}")

        if validation["invalid_urls"]:
            print(f"⚠️ Sample invalid URLs:")
            for invalid in validation["invalid_urls"]:
                print(f"   - {invalid}")

        # Process valid URLs and create sessions
        try:
            sessions_created = self.db.create_scraping_sessions_from_csv(csv_file)

            result = {
                "success": True,
                "sessions_created": sessions_created,
                "validation": validation,
                "dry_run": False
            }

            print(f"✅ CSV processing completed:")
            print(f"   Sessions created: {sessions_created}")

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Error creating sessions: {str(e)}",
                "sessions_created": 0,
                "validation": validation
            }

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get statistics about processed sessions"""
        stats = self.db.get_session_statistics()

        # Add derived statistics
        total = stats["total_sessions"]
        if total > 0:
            html_completed = stats["html_fetch_stats"].get("completed", 0)
            review_completed = stats["review_fetch_stats"].get("completed", 0)
            parsing_completed = stats["parsing_stats"].get("completed", 0)

            stats["completion_rates"] = {
                "html_fetch": (html_completed / total) * 100,
                "review_fetch": (review_completed / total) * 100,
                "parsing": (parsing_completed / total) * 100,
                "overall": (parsing_completed / total) * 100
            }

            stats["pending_counts"] = {
                "html_fetch": stats["html_fetch_stats"].get("pending", 0),
                "review_fetch": stats["review_fetch_stats"].get("pending", 0),
                "parsing": stats["parsing_stats"].get("pending", 0)
            }

        return stats

    def print_detailed_statistics(self):
        """Print comprehensive statistics"""
        stats = self.get_processing_statistics()

        print(f"\n📊 SCRAPING SESSIONS STATISTICS")
        print("=" * 50)

        if stats["total_sessions"] == 0:
            print("No sessions found in database")
            return

        print(f"📈 OVERALL:")
        print(f"   Total sessions: {stats['total_sessions']}")

        if "completion_rates" in stats:
            rates = stats["completion_rates"]
            print(f"   Overall completion: {rates['overall']:.1f}%")
            print(f"   HTML fetch rate: {rates['html_fetch']:.1f}%")
            print(f"   Review fetch rate: {rates['review_fetch']:.1f}%")
            print(f"   Parsing rate: {rates['parsing']:.1f}%")

        print(f"\n🔍 HTML FETCH STATUS:")
        for status, count in stats["html_fetch_stats"].items():
            print(f"   {status}: {count}")

        print(f"\n📊 REVIEW FETCH STATUS:")
        for status, count in stats["review_fetch_stats"].items():
            print(f"   {status}: {count}")

        print(f"\n🔄 PARSING STATUS:")
        for status, count in stats["parsing_stats"].items():
            print(f"   {status}: {count}")

        print(f"\n❌ FAILED (3+ attempts):")
        print(f"   HTML fetch failures: {stats['html_failed_count']}")
        print(f"   Review fetch failures: {stats['review_failed_count']}")

        if "pending_counts" in stats:
            pending = stats["pending_counts"]
            print(f"\n⏳ PENDING WORK:")
            print(f"   HTML fetch pending: {pending['html_fetch']}")
            print(f"   Review fetch pending: {pending['review_fetch']}")
            print(f"   Parsing pending: {pending['parsing']}")

def main():
    """Main CLI interface for CSV processing"""
    print("📄 CSV PROCESSOR FOR NEWEGG SCRAPER")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python csv_processor.py <csv_file> [--dry-run]")
        print("  python csv_processor.py --create-sample [filename]")
        print("  python csv_processor.py --stats")
        print()
        print("Examples:")
        print("  python csv_processor.py urls.csv")
        print("  python csv_processor.py urls.csv --dry-run")
        print("  python csv_processor.py --create-sample sample.csv")
        print("  python csv_processor.py --stats")
        return

    processor = CSVProcessor()

    if sys.argv[1] == "--stats":
        processor.print_detailed_statistics()
        return

    # Process CSV file
    csv_file = sys.argv[1]


    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return

    result = processor.process_csv_file(csv_file)

    if result["success"]:

        print(f"\n🎉 SUCCESS!")
        print(f"📄 CSV file processed: {csv_file}")
        print(f"✅ Sessions created: {result['sessions_created']}")
        print(f"💡 Next step: Run the scraper daemon to process these URLs")

    else:
        print(f"\n❌ FAILED: {result['error']}")

if __name__ == "__main__":
    main()