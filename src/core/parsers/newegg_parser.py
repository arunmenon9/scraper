#!/usr/bin/env python3
"""
Data Parser Service
Processes saved raw HTML and API responses from the unified scraper
Extracts structured data and saves to JSON, with optional database updates
"""

import os
import sys
import json
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from core.database.database import DatabaseHandler

@dataclass
class ProductInfo:
    title: str
    brand: str
    price: str
    rating: str
    reviews_count: str
    description: str
    newegg_item_number: str = ""
    item_number: str = ""

@dataclass
class Review:
    reviewer_name: str
    rating: str
    review_title: str
    review_body: str
    date: str
    verified_buyer: bool
    helpful_count: Optional[str] = None
    pros: Optional[str] = None
    cons: Optional[str] = None
    purchase_mark: Optional[str] = None
    total_voting: Optional[int] = None
    vendor_reply: Optional[bool] = None
    item_number: Optional[int] = None
    brand: Optional[str] = None
    product_description: Optional[str] = None

class NeweggParser:
    def __init__(self, enable_database=False):
        self.enable_database = enable_database
        self.db_connection = None

        if self.enable_database:
            self.setup_database()

    def setup_database(self):
        """Setup database connection"""
        try:
            self.db_connection = DatabaseHandler()
            print("✅ Database connection established")
        except Exception as e:
            print(f"⚠️ Database setup failed: {e}")
            self.enable_database = False

    def parse_session_data(self, session_dir: str, output_file: str = None) -> Dict[str, Any]:
        """
        Parse all data from a scraping session directory
        Returns structured data and optionally saves to JSON and database
        """
        print(f"🔍 DATA PARSER SERVICE")
        print("=" * 50)
        print(f"📁 Session directory: {session_dir}")

        if not os.path.exists(session_dir):
            raise ValueError(f"Session directory does not exist: {session_dir}")

        # Load session metadata
        metadata_file = os.path.join(session_dir, "metadata", "session_metadata.json")
        if not os.path.exists(metadata_file):
            raise ValueError(f"Session metadata not found: {metadata_file}")

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        print(f"📦 Product ID: {metadata.get('product_id', 'Unknown')}")
        print(f"🆔 Session ID: {metadata.get('session_id', 'Unknown')}")
        print(f"🔗 Product URL: {metadata.get('product_url', 'Unknown')}")

        parsed_data = {
            "metadata": metadata,
            "product_info": None,
            "reviews": [],
            "parsing_summary": {
                "html_files_processed": 0,
                "api_files_processed": 0,
                "total_reviews_parsed": 0,
                "parsing_timestamp": datetime.now().isoformat()
            }
        }

        try:
            # Step 1: Parse HTML data
            print(f"\n🔍 STEP 1: Parsing HTML data...")
            print("-" * 40)

            html_dir = os.path.join(session_dir, "html")
            if os.path.exists(html_dir):
                product_info = self.parse_html_files(html_dir)
                if product_info:
                    parsed_data["product_info"] = asdict(product_info)
                    print("✅ Product info extracted from HTML")
                else:
                    print("⚠️ No product info extracted from HTML")

            # Step 2: Parse API responses
            print(f"\n📊 STEP 2: Parsing API responses...")
            print("-" * 40)

            api_dir = os.path.join(session_dir, "api_responses")
            if os.path.exists(api_dir):
                api_reviews = self.parse_api_responses(api_dir)
                parsed_data["reviews"] = api_reviews
                parsed_data["parsing_summary"]["total_reviews_parsed"] = len(api_reviews)
                print(f"✅ {len(api_reviews)} reviews extracted from API responses")
            else:
                print("⚠️ No API response directory found")

            # Step 3: Save parsed data
            print(f"\n💾 STEP 3: Saving parsed data...")
            print("-" * 40)

            if not output_file:
                output_file = os.path.join(session_dir, "parsed_data.json")

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Parsed data saved to: {output_file}")

            # Step 4: Database update (if enabled)
            if self.enable_database:
                print(f"\n🗄️ STEP 4: Updating database...")
                print("-" * 40)
                self.update_database(parsed_data)
            else:
                print(f"\n⏭️ STEP 4: Database updates disabled")

            # Summary
            print(f"\n🎉 PARSING COMPLETED SUCCESSFULLY!")
            print("=" * 50)
            summary = parsed_data["parsing_summary"]
            print(f"📄 HTML files processed: {summary['html_files_processed']}")
            print(f"📊 API files processed: {summary['api_files_processed']}")
            print(f"💬 Reviews parsed: {summary['total_reviews_parsed']}")

            if parsed_data["product_info"]:
                product = parsed_data["product_info"]
                print(f"\n📦 PRODUCT SUMMARY:")
                print(f"   Title: {product['title'][:60]}{'...' if len(product['title']) > 60 else ''}")
                print(f"   Brand: {product['brand']}")
                print(f"   Price: {product['price']}")
                print(f"   Rating: {product['rating']}")
                print(f"   Reviews Count: {product['reviews_count']}")

            return parsed_data

        except Exception as e:
            print(f"❌ Error during parsing: {e}")
            parsed_data["parsing_summary"]["error"] = str(e)

            # Save partial data
            error_file = os.path.join(session_dir, "parsed_data_error.json")
            with open(error_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)

            print(f"💾 Partial data saved to: {error_file}")
            raise

    def parse_html_files(self, html_dir: str) -> Optional[ProductInfo]:
        """Parse product information from HTML files"""
        html_files = [f for f in os.listdir(html_dir) if f.endswith('.html')]

        if not html_files:
            print("⚠️ No HTML files found")
            return None

        # Try to find successful response file first
        preferred_files = [f for f in html_files if 'successful_response' in f]
        if not preferred_files:
            preferred_files = [f for f in html_files if 'final_response' in f]
        if not preferred_files:
            preferred_files = html_files

        html_file = os.path.join(html_dir, preferred_files[0])
        print(f"📄 Processing: {preferred_files[0]}")

        try:
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

            # Extract Newegg item number from URL patterns in the HTML
            newegg_item_number = ""
            item_number = ""

            # Look for item number patterns in the HTML
            item_patterns = [
                r'N82E16\d+',
                r'"ItemNumber"\s*:\s*"([^"]+)"',
                r'"NeweggItemNumber"\s*:\s*"([^"]+)"',
                r'/p/([A-Z0-9\-]+)',  # Extract from URL path like /p/14S-0041-002X9
                r'data-product-item="([^"]+)"',  # HTML data attributes
                r'itemNumber["\']?\s*[:=]\s*["\']?([A-Z0-9\-]+)',  # Various JS patterns
                r'product[_\-]?id["\']?\s*[:=]\s*["\']?([A-Z0-9\-]+)'  # Product ID patterns
            ]

            for pattern in item_patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    newegg_item_number = matches[0]
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

            product_info = ProductInfo(
                title=title,
                brand=brand,
                price=price,
                rating=rating,
                reviews_count=reviews_count,
                description=description,
                newegg_item_number=newegg_item_number,
                item_number=item_number
            )

            print(f"✅ Extracted product info:")
            print(f"   Title: {title[:50]}{'...' if len(title) > 50 else ''}")
            print(f"   Brand: {brand}")
            print(f"   Price: {price}")
            print(f"   Rating: {rating}")

            return product_info

        except Exception as e:
            print(f"❌ Error parsing HTML file {html_file}: {e}")
            return None

    def parse_api_responses(self, api_dir: str) -> List[Dict[str, Any]]:
        """Parse reviews from API response files"""
        all_reviews = []
        api_files = [f for f in os.listdir(api_dir) if f.startswith('reviews_page_') and f.endswith('_response.json')]
        api_files.sort()  # Process in order

        print(f"📊 Found {len(api_files)} API response files")

        for api_file in api_files:
            file_path = os.path.join(api_dir, api_file)
            print(f"📄 Processing: {api_file}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    response_data = json.load(f)

                if not response_data.get('success', False):
                    print(f"⚠️ Skipping failed response: {api_file}")
                    continue

                api_data = response_data.get('data', {})
                page_reviews = self.extract_reviews_from_api_data(api_data)
                all_reviews.extend(page_reviews)

                print(f"✅ Extracted {len(page_reviews)} reviews from {api_file}")

            except Exception as e:
                print(f"❌ Error parsing {api_file}: {e}")
                continue

        return all_reviews

    def extract_reviews_from_api_data(self, api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and parse reviews from API response data"""
        reviews = []

        # Look for reviews in the response
        reviews_data = None

        if 'SearchResult' in api_data and api_data['SearchResult']:
            search_result = api_data['SearchResult']
            if 'CustomerReviewList' in search_result and search_result['CustomerReviewList']:
                reviews_data = search_result['CustomerReviewList']

        if reviews_data:
            for review_item in reviews_data:
                review = self.parse_single_review(review_item)
                if review:
                    reviews.append(asdict(review))

        return reviews

    def parse_single_review(self, review_data: Dict[str, Any]) -> Optional[Review]:
        """Parse individual review from API response data"""
        try:
            # Extract reviewer name
            reviewer_name = review_data.get('DisplayName') or review_data.get('NickName', 'Anonymous')

            # Extract rating
            rating = str(review_data.get('Rating', 0))

            # Extract title and comments
            title = review_data.get('Title', '').strip()
            comments = review_data.get('Comments', '').strip()

            # Extract date
            date = review_data.get('InDate', '')
            if date and 'T' in date:
                date = date.split('T')[0]

            # Check if verified buyer
            verified = review_data.get('HasPurchased', False)

            # Extract helpful count
            helpful_count = review_data.get('TotalConsented')
            helpful_str = str(helpful_count) if helpful_count is not None else None

            # Extract pros and cons
            pros = review_data.get('Pros', '').strip() if review_data.get('Pros') else None
            cons = review_data.get('Cons', '').strip() if review_data.get('Cons') else None

            # Extract additional fields
            purchase_mark = review_data.get('PurchaseMark')
            total_voting = review_data.get('TotalVoting')
            vendor_reply = review_data.get('HasVendorReplay')
            item_number = review_data.get('ItemNumber')
            brand = review_data.get('BrandDescription')
            product_description = review_data.get('ItemDescription')

            return Review(
                reviewer_name=reviewer_name,
                rating=rating,
                review_title=title,
                review_body=comments,
                date=date,
                verified_buyer=verified,
                helpful_count=helpful_str,
                pros=pros,
                cons=cons,
                purchase_mark=purchase_mark,
                total_voting=total_voting,
                vendor_reply=vendor_reply,
                item_number=item_number,
                brand=brand,
                product_description=product_description
            )

        except Exception as e:
            print(f"⚠️ Error parsing individual review: {e}")
            return None

    def update_database(self, parsed_data: Dict[str, Any]):
        """Update database with parsed data"""
        if not self.db_connection:
            print("⚠️ No database connection available")
            return

        try:
            # Insert/update product
            product_id = None
            if parsed_data["product_info"]:
                product_url = parsed_data["metadata"].get("product_url", "")
                product_id = self.db_connection.insert_or_update_product(
                    parsed_data["product_info"], product_url
                )
                print(f"✅ Product updated in database (ID: {product_id})")

            # Insert reviews
            if parsed_data["reviews"] and product_id:
                inserted_count = self.db_connection.insert_reviews(product_id, parsed_data["reviews"])
                print(f"✅ {inserted_count} reviews inserted into database")

            # Insert session record
            session_id = self.db_connection.insert_scraping_session(parsed_data["metadata"])
            print(f"✅ Scraping session recorded (ID: {session_id})")

            # Show database stats
            stats = self.db_connection.get_product_stats()
            print(f"📊 Database now contains:")
            print(f"   - {stats['total_products']} products")
            print(f"   - {stats['total_reviews']} reviews")
            print(f"   - {stats['total_sessions']} sessions")

        except Exception as e:
            print(f"❌ Database update failed: {e}")

def find_session_directories(base_dir="raw_data"):
    """Find all session directories in the raw data folder"""
    if not os.path.exists(base_dir):
        return []

    session_dirs = []
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "metadata")):
            session_dirs.append(item_path)

    return sorted(session_dirs, reverse=True)  # Most recent first

def main():
    print("🔍 DATA PARSER SERVICE")
    print("=" * 50)

    if len(sys.argv) > 1:
        session_dir = sys.argv[1]
        if not os.path.exists(session_dir):
            print(f"❌ Session directory does not exist: {session_dir}")
            return
    else:
        # Auto-detect most recent session
        session_dirs = find_session_directories()
        if not session_dirs:
            print("❌ No session directories found in raw_data/")
            print("💡 Run the unified_scraper_service.py first to generate raw data")
            return

        session_dir = session_dirs[0]
        print(f"🔍 Auto-detected most recent session: {os.path.basename(session_dir)}")

    # Optional: output file argument
    output_file = None
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    # Optional: database flag
    enable_database = len(sys.argv) > 3 and sys.argv[3].lower() in ['true', '1', 'yes']

    parser = NeweggParser(enable_database=enable_database)

    try:
        result = parser.parse_session_data(session_dir, output_file)

        print(f"\n🎯 SUCCESS! Data parsing completed.")

        if result["reviews"]:
            print(f"💬 Sample review:")
            sample = result["reviews"][0]
            print(f"   👤 {sample['reviewer_name']} - ⭐ {sample['rating']}/5")
            print(f"   📋 {sample['review_title'][:50]}{'...' if len(sample['review_title']) > 50 else ''}")

    except Exception as e:
        print(f"❌ FAILED: {e}")

if __name__ == "__main__":
    main()