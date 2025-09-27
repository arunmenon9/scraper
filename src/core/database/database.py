#!/usr/bin/env python3
"""
Database Handler for Newegg Scraper
Handles database operations for products and reviews
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

class DatabaseHandler:
    def __init__(self, db_path: str = "newegg_scraper.db"):
        # Always use absolute path to avoid issues with changing working directories
        if not os.path.isabs(db_path):
            self.db_path = os.path.abspath(db_path)
        else:
            self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Products table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    newegg_item_number TEXT UNIQUE,
                    item_number TEXT,
                    title TEXT,
                    brand TEXT,
                    price TEXT,
                    rating TEXT,
                    reviews_count TEXT,
                    description TEXT,
                    product_url TEXT,
                    session_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Reviews table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    reviewer_name TEXT,
                    rating TEXT,
                    review_title TEXT,
                    review_body TEXT,
                    date TEXT,
                    verified_buyer BOOLEAN,
                    helpful_count TEXT,
                    pros TEXT,
                    cons TEXT,
                    purchase_mark TEXT,
                    total_voting INTEGER,
                    vendor_reply BOOLEAN,
                    item_number INTEGER,
                    brand TEXT,
                    product_description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')

            # Scraping sessions table for tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraping_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    product_id INTEGER,
                    product_url TEXT,
                    html_fetch_status TEXT DEFAULT 'pending',
                    review_fetch_status TEXT DEFAULT 'pending',
                    html_fetch_attempts INTEGER DEFAULT 0,
                    review_fetch_attempts INTEGER DEFAULT 0,
                    html_error_message TEXT,
                    review_error_message TEXT,
                    parsing_status TEXT DEFAULT 'pending',
                    html_file_location TEXT,
                    review_data_location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scraped_at TIMESTAMP,
                    parsed_at TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')

            conn.commit()
            print(f"✅ Database initialized: {self.db_path}")

    def insert_or_update_product(self, product_info: Dict[str, Any], product_url: str = "", session_id: str = None) -> int:
        """Insert or update product information, return product ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if product already exists
            cursor.execute(
                "SELECT id FROM products WHERE newegg_item_number = ? OR title = ?",
                (product_info.get('newegg_item_number', ''), product_info.get('title', ''))
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing product
                product_id = existing[0]
                cursor.execute('''
                    UPDATE products SET
                        item_number = ?, title = ?, brand = ?, price = ?, rating = ?,
                        reviews_count = ?, description = ?, product_url = ?, session_id = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (
                    product_info.get('item_number', ''),
                    product_info.get('title', ''),
                    product_info.get('brand', ''),
                    product_info.get('price', ''),
                    product_info.get('rating', ''),
                    product_info.get('reviews_count', ''),
                    product_info.get('description', ''),
                    product_url,
                    session_id,
                    product_id
                ))
                print(f"✅ Updated existing product ID: {product_id}")
            else:
                # Insert new product
                cursor.execute('''
                    INSERT INTO products (
                        newegg_item_number, item_number, title, brand, price, rating,
                        reviews_count, description, product_url, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_info.get('newegg_item_number', ''),
                    product_info.get('item_number', ''),
                    product_info.get('title', ''),
                    product_info.get('brand', ''),
                    product_info.get('price', ''),
                    product_info.get('rating', ''),
                    product_info.get('reviews_count', ''),
                    product_info.get('description', ''),
                    product_url,
                    session_id
                ))
                product_id = cursor.lastrowid
                print(f"✅ Inserted new product ID: {product_id}")

            conn.commit()
            return product_id

    def insert_reviews(self, product_id: int, reviews: List[Dict[str, Any]]) -> int:
        """Insert reviews for a product, return count of inserted reviews"""
        if not reviews:
            return 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            inserted_count = 0

            for review in reviews:
                # Check for duplicate reviews (basic deduplication by title and reviewer)
                cursor.execute('''
                    SELECT id FROM reviews
                    WHERE product_id = ? AND reviewer_name = ? AND review_title = ?
                ''', (product_id, review.get('reviewer_name', ''), review.get('review_title', '')))

                if cursor.fetchone():
                    continue  # Skip duplicate

                # Insert review
                cursor.execute('''
                    INSERT INTO reviews (
                        product_id, reviewer_name, rating, review_title, review_body,
                        date, verified_buyer, helpful_count, pros, cons, purchase_mark,
                        total_voting, vendor_reply, item_number, brand, product_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_id,
                    review.get('reviewer_name', ''),
                    review.get('rating', ''),
                    review.get('review_title', ''),
                    review.get('review_body', ''),
                    review.get('date', ''),
                    review.get('verified_buyer', False),
                    review.get('helpful_count'),
                    review.get('pros'),
                    review.get('cons'),
                    review.get('purchase_mark'),
                    review.get('total_voting'),
                    review.get('vendor_reply'),
                    review.get('item_number'),
                    review.get('brand'),
                    review.get('product_description')
                ))
                inserted_count += 1

            conn.commit()
            print(f"✅ Inserted {inserted_count} new reviews (skipped {len(reviews) - inserted_count} duplicates)")
            return inserted_count

    def create_scraping_sessions_from_csv(self, csv_file: str) -> int:
        """Create scraping session records from CSV file"""
        import csv
        from datetime import datetime

        inserted_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    product_url = row.get('url', '').strip()
                    if not product_url:
                        continue

                    # Extract product ID from URL (value after p/)
                    product_id = None
                    import re
                    product_match = re.search(r'/p/([^/?]+)', product_url)
                    if product_match:
                        product_id = product_match.group(1)

                    # Generate unique session ID
                    session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{inserted_count:04d}"

                    # Check if URL already exists in pending state
                    cursor.execute('''
                        SELECT id FROM scraping_sessions
                        WHERE product_url = ? AND
                        (html_fetch_status = 'pending' OR review_fetch_status = 'pending' OR parsing_status = 'pending')
                    ''', (product_url,))

                    if cursor.fetchone():
                        print(f"⚠️ Skipping duplicate pending URL: {product_url}")
                        continue


                    cursor.execute('''
                        INSERT INTO scraping_sessions (
                            session_id, product_id, product_url, html_fetch_status, review_fetch_status, parsing_status
                        ) VALUES (?, ?, ?, 'pending', 'pending', 'pending')
                    ''', (session_id, product_id, product_url))

                    inserted_count += 1

                    print(f"✅ Session {inserted_count}: Product ID {product_id}")

            conn.commit()

        print(f"✅ Created {inserted_count} scraping session records from {csv_file}")
        return inserted_count

    def get_pending_html_fetch_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get sessions that need HTML fetching"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, session_id, product_url, html_fetch_attempts, html_error_message
                FROM scraping_sessions
                WHERE html_fetch_status = 'pending' AND html_fetch_attempts < 3
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "product_url": row[2],
                    "html_fetch_attempts": row[3],
                    "html_error_message": row[4]
                }
                for row in rows
            ]

    def get_pending_review_fetch_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get sessions that need review fetching"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, session_id, product_url, review_fetch_attempts, review_error_message, html_file_location
                FROM scraping_sessions
                WHERE html_fetch_status = 'completed' AND review_fetch_status = 'pending'
                AND review_fetch_attempts < 3
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "product_url": row[2],
                    "review_fetch_attempts": row[3],
                    "review_error_message": row[4],
                    "html_file_location": row[5]
                }
                for row in rows
            ]

    def get_ready_for_parsing_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get sessions ready for parsing - only those with successful HTML fetch"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, session_id, product_url, html_file_location, review_data_location
                FROM scraping_sessions
                WHERE html_fetch_status = 'completed'
                AND (review_fetch_status = 'completed' OR review_fetch_status = 'failed')
                AND parsing_status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "product_url": row[2],
                    "html_file_location": row[3],
                    "review_data_location": row[4]
                }
                for row in rows
            ]

    def update_html_fetch_status(self, session_id: int, status: str, file_location: str = None, error_message: str = None):
        """Update HTML fetch status for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get current attempt count
            cursor.execute('SELECT html_fetch_attempts FROM scraping_sessions WHERE id = ?', (session_id,))
            current_attempts = cursor.fetchone()[0] + 1

            if status == 'completed':
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET html_fetch_attempts = ?, html_fetch_status = ?,
                        html_file_location = ?, html_error_message = NULL, scraped_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (current_attempts, status, file_location, session_id))
            else:  # Failed attempt
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET html_fetch_attempts = ?, html_error_message = ?
                    WHERE id = ?
                ''', (current_attempts, error_message, session_id))

                # If this was the 3rd attempt, mark as permanently failed
                if current_attempts >= 3:
                    cursor.execute('''
                        UPDATE scraping_sessions
                        SET html_fetch_status = 'failed'
                        WHERE id = ?
                    ''', (session_id,))
                    print(f"⚠️ HTML fetch failed permanently after {current_attempts} attempts")
                else:
                    # Keep as pending for retry in next cycle
                    print(f"⚠️ HTML fetch attempt {current_attempts}/3 failed, will retry")

            conn.commit()

    def update_review_fetch_status(self, session_id: int, status: str, data_location: str = None, error_message: str = None):
        """Update review fetch status for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get current attempt count
            cursor.execute('SELECT review_fetch_attempts FROM scraping_sessions WHERE id = ?', (session_id,))
            current_attempts = cursor.fetchone()[0] + 1

            if status == 'completed':
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET review_fetch_attempts = ?, review_fetch_status = ?,
                        review_data_location = ?, review_error_message = NULL
                    WHERE id = ?
                ''', (current_attempts, status, data_location, session_id))
            else:  # Failed attempt
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET review_fetch_attempts = ?, review_error_message = ?
                    WHERE id = ?
                ''', (current_attempts, error_message, session_id))

                # If this was the 3rd attempt, mark as permanently failed
                if current_attempts >= 3:
                    cursor.execute('''
                        UPDATE scraping_sessions
                        SET review_fetch_status = 'failed', review_data_location = NULL
                        WHERE id = ?
                    ''', (session_id,))
                    print(f"⚠️ Review fetch failed permanently after {current_attempts} attempts")
                else:
                    # Keep as pending for retry in next cycle
                    print(f"⚠️ Review fetch attempt {current_attempts}/3 failed, will retry")

            conn.commit()

    def update_parsing_status(self, session_id: int, status: str, error_message: str = None):
        """Update parsing status for a session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if status == 'completed':
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET parsing_status = ?, parsed_at = CURRENT_TIMESTAMP, processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, session_id))
            elif status == 'failed':
                cursor.execute('''
                    UPDATE scraping_sessions
                    SET parsing_status = ?, html_error_message = COALESCE(html_error_message, ?) ||
                    CASE WHEN html_error_message IS NOT NULL THEN '; Parsing: ' || ? ELSE ? END
                    WHERE id = ?
                ''', (status, error_message, error_message, error_message, session_id))

            conn.commit()

    def get_session_statistics(self) -> Dict[str, Any]:
        """Get comprehensive session statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Count by HTML fetch status
            cursor.execute('''
                SELECT html_fetch_status, COUNT(*)
                FROM scraping_sessions
                GROUP BY html_fetch_status
            ''')
            html_stats = dict(cursor.fetchall())

            # Count by review fetch status
            cursor.execute('''
                SELECT review_fetch_status, COUNT(*)
                FROM scraping_sessions
                GROUP BY review_fetch_status
            ''')
            review_stats = dict(cursor.fetchall())

            # Count by parsing status
            cursor.execute('''
                SELECT parsing_status, COUNT(*)
                FROM scraping_sessions
                GROUP BY parsing_status
            ''')
            parsing_stats = dict(cursor.fetchall())

            # Failed sessions (3+ attempts)
            cursor.execute('''
                SELECT COUNT(*) FROM scraping_sessions
                WHERE html_fetch_attempts >= 3 AND html_fetch_status != 'completed'
            ''')
            html_failed = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM scraping_sessions
                WHERE review_fetch_attempts >= 3 AND review_fetch_status != 'completed'
            ''')
            review_failed = cursor.fetchone()[0]

            return {
                "html_fetch_stats": html_stats,
                "review_fetch_stats": review_stats,
                "parsing_stats": parsing_stats,
                "html_failed_count": html_failed,
                "review_failed_count": review_failed,
                "total_sessions": sum(html_stats.values())
            }

    def insert_scraping_session(self, metadata: Dict[str, Any]) -> int:
        """Insert scraping session record, return session record ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get product_id if available
            product_id = None
            if metadata.get('product_url'):
                cursor.execute("SELECT id FROM products WHERE product_url = ?", (metadata['product_url'],))
                result = cursor.fetchone()
                if result:
                    product_id = result[0]

            cursor.execute('''
                INSERT INTO scraping_sessions (
                    session_id, product_id, product_url, status, start_time, end_time,
                    reviews_extracted, reviews_available, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metadata.get('session_id', ''),
                product_id,
                metadata.get('product_url', ''),
                metadata.get('status', ''),
                metadata.get('start_time', ''),
                metadata.get('end_time', ''),
                metadata.get('total_reviews_extracted', 0),
                metadata.get('total_reviews_available', 0),
                metadata.get('error', '')
            ))

            session_record_id = cursor.lastrowid
            conn.commit()
            print(f"✅ Inserted scraping session record ID: {session_record_id}")
            return session_record_id

    def get_product_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Product count
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()[0]

            # Review count
            cursor.execute("SELECT COUNT(*) FROM reviews")
            review_count = cursor.fetchone()[0]

            # Session count
            cursor.execute("SELECT COUNT(*) FROM scraping_sessions")
            session_count = cursor.fetchone()[0]

            # Recent sessions
            cursor.execute('''
                SELECT session_id, product_url, status, reviews_extracted
                FROM scraping_sessions
                ORDER BY created_at DESC
                LIMIT 5
            ''')
            recent_sessions = cursor.fetchall()

            return {
                "total_products": product_count,
                "total_reviews": review_count,
                "total_sessions": session_count,
                "recent_sessions": [
                    {
                        "session_id": row[0],
                        "product_url": row[1],
                        "status": row[2],
                        "reviews_extracted": row[3]
                    }
                    for row in recent_sessions
                ]
            }

    def get_product_by_url(self, product_url: str) -> Optional[Dict[str, Any]]:
        """Get product information by URL"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, newegg_item_number, title, brand, price, rating,
                       reviews_count, description, created_at, updated_at
                FROM products WHERE product_url = ?
            ''', (product_url,))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "newegg_item_number": row[1],
                    "title": row[2],
                    "brand": row[3],
                    "price": row[4],
                    "rating": row[5],
                    "reviews_count": row[6],
                    "description": row[7],
                    "created_at": row[8],
                    "updated_at": row[9]
                }
            return None

    def get_reviews_for_product(self, product_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get reviews for a specific product"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT reviewer_name, rating, review_title, review_body, date,
                       verified_buyer, helpful_count, pros, cons, created_at
                FROM reviews
                WHERE product_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (product_id, limit))

            rows = cursor.fetchall()
            return [
                {
                    "reviewer_name": row[0],
                    "rating": row[1],
                    "review_title": row[2],
                    "review_body": row[3],
                    "date": row[4],
                    "verified_buyer": bool(row[5]),
                    "helpful_count": row[6],
                    "pros": row[7],
                    "cons": row[8],
                    "created_at": row[9]
                }
                for row in rows
            ]

    def get_product_count(self) -> int:
        """Get total product count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            return cursor.fetchone()[0]

    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sessions for web interface"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, session_id, product_url, html_fetch_status, review_fetch_status,
                       parsing_status, created_at
                FROM scraping_sessions
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "product_url": row[2],
                    "html_status": row[3],
                    "review_status": row[4],
                    "parsing_status": row[5],
                    "created_at": row[6]
                }
                for row in rows
            ]

    def get_products_paginated(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get products with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get total count
            cursor.execute("SELECT COUNT(*) FROM products")
            total = cursor.fetchone()[0]

            # Get products for current page
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT id, newegg_item_number, title, brand, price, rating,
                       reviews_count, created_at
                FROM products
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))

            rows = cursor.fetchall()
            products = [
                {
                    "id": row[0],
                    "newegg_item_number": row[1],
                    "title": row[2],
                    "brand": row[3],
                    "price": row[4],
                    "rating": row[5],
                    "reviews_count": row[6],
                    "created_at": row[7]
                }
                for row in rows
            ]

            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages

            return {
                "products": products,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next,
                    "prev_num": page - 1 if has_prev else None,
                    "next_num": page + 1 if has_next else None
                }
            }

    def get_sessions_paginated(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get sessions with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get total count
            cursor.execute("SELECT COUNT(*) FROM scraping_sessions")
            total = cursor.fetchone()[0]

            # Get sessions for current page
            offset = (page - 1) * per_page
            cursor.execute('''
                SELECT id, session_id, product_url, html_fetch_status, review_fetch_status,
                       parsing_status, created_at, scraped_at
                FROM scraping_sessions
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (per_page, offset))

            rows = cursor.fetchall()
            sessions = [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "product_url": row[2],
                    "html_status": row[3],
                    "review_status": row[4],
                    "parsing_status": row[5],
                    "created_at": row[6],
                    "scraped_at": row[7]
                }
                for row in rows
            ]

            # Calculate pagination info
            total_pages = (total + per_page - 1) // per_page
            has_prev = page > 1
            has_next = page < total_pages

            return {
                "sessions": sessions,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages,
                    "has_prev": has_prev,
                    "has_next": has_next,
                    "prev_num": page - 1 if has_prev else None,
                    "next_num": page + 1 if has_next else None
                }
            }

    def get_product_by_id(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get product by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, newegg_item_number, item_number, title, brand, price,
                       rating, reviews_count, description, product_url, session_id,
                       created_at, updated_at
                FROM products
                WHERE id = ?
            ''', (product_id,))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "newegg_item_number": row[1],
                    "item_number": row[2],
                    "title": row[3],
                    "brand": row[4],
                    "price": row[5],
                    "rating": row[6],
                    "reviews_count": row[7],
                    "description": row[8],
                    "product_url": row[9],
                    "session_id": row[10],
                    "created_at": row[11],
                    "updated_at": row[12]
                }
            return None

    def get_reviews_by_product_id(self, product_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        """Get reviews for a product by product ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, reviewer_name, rating, review_title, review_body, date,
                       verified_buyer, helpful_count, pros, cons, created_at
                FROM reviews
                WHERE product_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (product_id, limit))

            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "reviewer_name": row[1],
                    "rating": row[2],
                    "review_title": row[3],
                    "review_body": row[4],
                    "date": row[5],
                    "verified_buyer": bool(row[6]),
                    "helpful_count": row[7],
                    "pros": row[8],
                    "cons": row[9],
                    "created_at": row[10]
                }
                for row in rows
            ]

def main():
    """Test database functionality"""
    print("🗄️ DATABASE HANDLER TEST")
    print("=" * 40)

    db = DatabaseHandler("test_newegg.db")

    # Get stats
    stats = db.get_product_stats()
    print(f"📊 Database Stats:")
    print(f"   Products: {stats['total_products']}")
    print(f"   Reviews: {stats['total_reviews']}")
    print(f"   Sessions: {stats['total_sessions']}")

    # Test product insertion
    test_product = {
        "newegg_item_number": "N82E16824281334",
        "item_number": "24-281-334",
        "title": "Test Gaming Monitor",
        "brand": "ASUS",
        "price": "$299.99",
        "rating": "4.5",
        "reviews_count": "(123)",
        "description": "Test gaming monitor description"
    }

    product_id = db.insert_or_update_product(test_product, "https://test.url")

    # Test review insertion
    test_reviews = [
        {
            "reviewer_name": "TestUser1",
            "rating": "5",
            "review_title": "Great monitor!",
            "review_body": "Love this monitor, great for gaming.",
            "date": "2024-12-15",
            "verified_buyer": True,
            "helpful_count": "5"
        }
    ]

    db.insert_reviews(product_id, test_reviews)

    print("✅ Database test completed successfully!")

if __name__ == "__main__":
    main()