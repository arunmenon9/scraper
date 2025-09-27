#!/usr/bin/env python3
"""
Newegg Reviews Fetcher
Fetches reviews using the ProductReview API endpoint
"""

import requests
import json
import re
import sys
from urllib.parse import quote
from dataclasses import dataclass, asdict
from typing import List, Optional

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

class NeweggReviewsFetcher:
    def __init__(self, existing_session=None):
        if existing_session:
            self.session = existing_session
            self._using_existing_session = True
            print("🔄 Using existing session with cookies - keeping all headers as-is")
            # Debug: Print session state
            self._debug_session_state("INHERITED")
            # Don't modify headers at all - keep them exactly as they worked for HTML fetching
        else:
            self.session = requests.Session()
            self._using_existing_session = False
            self.setup_headers()
            self._debug_session_state("NEW")

    def setup_headers(self):
        """Setup session headers to mimic browser"""
        self.session.headers.update({
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'accept-encoding': 'gzip, deflate, br',
            'connection': 'keep-alive',
            'dnt': '1',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'cache-control': 'no-cache',
            'pragma': 'no-cache'
        })

    def _debug_session_state(self, context: str):
        """Debug session cookies and headers"""
        print(f"🔍 SESSION DEBUG ({context}):")
        print(f"   Cookies: {len(self.session.cookies)} items")
        for cookie in self.session.cookies:
            print(f"     - {cookie.name}: {cookie.value[:20]}{'...' if len(cookie.value) > 20 else ''} (domain: {cookie.domain})")

        print(f"   Headers: {len(self.session.headers)} items")
        for key, value in self.session.headers.items():
            if key.lower() in ['user-agent', 'referer', 'accept', 'cookie']:
                print(f"     - {key}: {value[:50]}{'...' if len(str(value)) > 50 else ''}")
        print()

    def setup_api_headers(self):
        """Setup headers specifically for API calls"""
        self.session.headers.update({
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en;q=0.9',
            'dnt': '1',
            'priority': 'u=1, i',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
        })

    def extract_product_info_from_url(self, product_url: str) -> dict:
        """Extract item number and other info from product URL"""
        # Extract item number from URL - handle both formats:
        # /p/N82E16824281334 (traditional format)
        # /p/3C6-0064-00002 (newer format)
        item_match = re.search(r'/p/([^/?]+)', product_url)
        if not item_match:
            raise ValueError(f"Could not extract item number from URL: {product_url}")

        raw_item_number = item_match.group(1)
        print(f"🔍 Extracted item number: {raw_item_number}")

        # Handle traditional N82E16... format
        if raw_item_number.startswith('N82E16'):
            newegg_item_number = raw_item_number

            # Extract the numerical part after N82E16 and format correctly
            number_match = re.search(r'N82E16(\d+)', newegg_item_number)
            if number_match:
                item_number = number_match.group(1)
                # Based on working example: N82E16820248142 -> item_number=820248142 -> "20-248-142"
                if len(item_number) >= 8:
                    if item_number.startswith('8'):
                        # Skip first digit: 820248142 -> 20248142
                        clean_number = item_number[1:]
                    else:
                        clean_number = item_number
                    # Now format as XX-XXX-XXX: 20248142 -> 20-248-142
                    formatted_item = f"{clean_number[:2]}-{clean_number[2:5]}-{clean_number[5:]}"
                else:
                    formatted_item = item_number
                print(f"🔍 Full item number: {item_number}")
                print(f"🔍 Formatted item number: {formatted_item}")
            else:
                formatted_item = newegg_item_number
        else:
            # Handle newer format like 3C6-0064-00002
            newegg_item_number = raw_item_number
            formatted_item = raw_item_number
            print(f"🔍 Using item number as-is: {formatted_item}")

        return {
            'newegg_item_number': newegg_item_number,
            'item_number': formatted_item,
            'item_group_id': None,  # Will need to be extracted from product page
            'subcategory_id': "3743"  # Default, will be updated from product page
        }

    def build_review_api_url(self, product_info: dict, page_index: int = 1, per_page: int = 100) -> str:
        """Build the ProductReview API URL with max 100 reviews per page"""

        # Create the review request parameters
        review_request = {
            "IsGetSummary": True,
            "IsGetTopReview": False,
            "IsGetItemProperty": True,
            "IsGetAllReviewCategory": False,
            "IsSearchWithoutStatistics": False,
            "IsGetFilterCount": False,
            "IsGetFeatures": True,
            "SearchProperty": {
                "CombineGroup": 3,
                "FilterDate": 0,
                "IsB2BExclusiveReviews": False,
                "IsBestCritialReview": False,
                "IsBestFavorableReview": False,
                "IsItemMarkOnly": False,
                "IsProductReviewSearch": True,
                "IsPurchaserReviewOnly": False,
                "IsResponsiveSite": False,
                "IsSmartPhone": False,
                "IsVendorResponse": False,
                "IsVideoReviewOnly": False,
                "ItemGroupId": product_info.get('item_group_id', 204644370),  # Default value
                "ItemNumber": product_info['item_number'],
                "NeweggItemNumber": product_info['newegg_item_number'],
                "PageIndex": page_index,
                "PerPageItemCount": per_page,
                "RatingReviewDisplayType": 0,
                "ReviewTimeFilterType": 0,
                "RatingType": -1,
                "ReviewType": 3,
                "SearchKeywords": "",
                "SearchLanguage": "",
                "SellerId": "",
                "SortOrderType": 1,
                "SubCategoryId": product_info.get('subcategory_id', "3743"),
                "TransNumber": 0,
                "WithImage": False,
                "HotKeyword": "",
                "HotKeywordList": [],
                "SearchkeywordsList": []
            }
        }

        # Convert to JSON and URL encode
        request_json = json.dumps(review_request, separators=(',', ':'))
        encoded_request = quote(request_json)

        api_url = f"https://www.newegg.com/product/api/ProductReview?reviewRequestStr={encoded_request}"
        return api_url

    def establish_session(self, product_url: str) -> bool:
        """Establish session by visiting main page and product page first with realistic delays"""
        try:
            print("🔄 Establishing session with Newegg...")
            import time

            # Step 1: Visit main page to get initial cookies
            main_page = "https://www.newegg.com"
            response = self.session.get(main_page, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Failed to visit main page: {response.status_code}")
                return False
            print(f"✅ Main page visited - Cookies received: {len(response.cookies)}")
            time.sleep(3)  # Longer delay

            # Step 2: Visit a category page (simulate realistic browsing)
            print(f"🔄 Browsing category page...")
            category_url = "https://www.newegg.com/Keyboards/Category/ID-63"
            response = self.session.get(category_url, timeout=15)
            if response.status_code == 200:
                print(f"✅ Category page visited")
            time.sleep(2)

            # Step 3: Visit product page multiple times (like a real user)
            print(f"🔄 Visiting product page...")
            response = self.session.get(product_url, timeout=15)
            if response.status_code != 200:
                print(f"⚠️ Failed to visit product page: {response.status_code}")
                return False
            print(f"✅ Product page visited - Total cookies: {len(self.session.cookies)}")
            time.sleep(2)

            # Step 4: Make another product page request (simulate user scrolling/staying)
            print(f"🔄 Revisiting product page...")
            response = self.session.get(product_url, timeout=15)
            print(f"✅ Product page revisited - Final cookies: {len(self.session.cookies)}")
            time.sleep(1)

            # Look for critical cookies
            critical_cookies = ['cf_clearance', '__cf_bm', 'NV%5FCONFIGURATION', 'NVTC']
            has_critical = False
            for cookie in self.session.cookies:
                if any(crit in cookie.name for crit in critical_cookies):
                    print(f"🔑 Critical cookie found: {cookie.name}")
                    has_critical = True

            if not has_critical:
                print(f"⚠️ Missing critical cookies - API may fail")
                # Try one more page to get Cloudflare clearance
                print(f"🔄 Trying to get Cloudflare clearance...")
                search_url = "https://www.newegg.com/p/pl?d=laptop"
                response = self.session.get(search_url, timeout=15)
                time.sleep(3)

            print(f"🍪 Final cookie count: {len(self.session.cookies)}")
            return True

        except Exception as e:
            print(f"⚠️ Error establishing session: {e}")
            return False

    def print_curl_equivalent(self, url: str):
        """Print the curl equivalent of the request for debugging"""
        print(f"\n🔧 CURL EQUIVALENT REQUEST:")
        print(f"curl '{url}' \\")

        # Print headers
        for name, value in self.session.headers.items():
            print(f"  -H '{name}: {value}' \\")

        # Print cookies
        if self.session.cookies:
            cookie_string = "; ".join([f"{cookie.name}={cookie.value}" for cookie in self.session.cookies])
            print(f"  -b '{cookie_string}' \\")

        print("  --compressed")
        print("</end of curl command>\n")

    def fetch_reviews(self, product_url: str, max_pages: int = 3) -> dict:
        """Fetch reviews for a product"""

        print(f"🔍 Extracting product info from: {product_url}")
        product_info = self.extract_product_info_from_url(product_url)
        print(f"📦 Product: {product_info['newegg_item_number']} ({product_info['item_number']})")

        # Check if we need to establish session
        if hasattr(self, '_using_existing_session') and self._using_existing_session:
            print("🔄 Using existing session - skipping session establishment")
        else:
            # Establish session first
            if not self.establish_session(product_url):
                print("⚠️ Proceeding without session establishment...")

        # Extract ItemGroupId and SubCategoryId using ProductRealtime API
        print("🔍 Extracting ItemGroupId and SubCategoryId using ProductRealtime API...")
        # try:
        #     # Build the ProductRealtime API URL
        #     realtime_api_url = f"https://www.newegg.com/product/api/ProductRealtime?ItemNumber={product_info['newegg_item_number']}"
        #     print(f"🌐 Calling ProductRealtime API: {realtime_api_url}")

        #     # Call ProductRealtime API exactly like a regular page request
        #     # No header modifications - use the session exactly as it worked for HTML
        #     response = self.session.get(realtime_api_url, timeout=10)

        #     print(f"📊 ProductRealtime API Response Status: {response.status_code}")

        #     if response.status_code == 200:
        #         try:
        #             realtime_data = response.json()
        #             print(f"✅ ProductRealtime API returned valid JSON")

        #             # Print the API response structure for debugging
        #             print(f"📊 API Response keys: {list(realtime_data.keys()) if isinstance(realtime_data, dict) else 'Not a dict'}")

        #             # Look for ItemGroupId in the response
        #             if isinstance(realtime_data, dict):
        #                 # Try different possible locations for ItemGroupId
        #                 item_group_id = None
        #                 subcategory_id = None

        #                 # Check direct keys
        #                 if 'ItemGroupId' in realtime_data:
        #                     item_group_id = realtime_data['ItemGroupId']
        #                 elif 'ItemGroupID' in realtime_data:
        #                     item_group_id = realtime_data['ItemGroupID']

        #                 # Check for SubCategoryId
        #                 if 'SubCategoryId' in realtime_data:
        #                     subcategory_id = realtime_data['SubCategoryId']
        #                 elif 'SubcategoryId' in realtime_data:
        #                     subcategory_id = realtime_data['SubcategoryId']

        #                 # Check in nested objects
        #                 for key, value in realtime_data.items():
        #                     if isinstance(value, dict):
        #                         if not item_group_id and 'ItemGroupId' in value:
        #                             item_group_id = value['ItemGroupId']
        #                         elif not item_group_id and 'ItemGroupID' in value:
        #                             item_group_id = value['ItemGroupID']

        #                         if not subcategory_id and 'SubCategoryId' in value:
        #                             subcategory_id = value['SubCategoryId']
        #                         elif not subcategory_id and 'SubcategoryId' in value:
        #                             subcategory_id = value['SubcategoryId']

        #                 # Update product_info with found values
        #                 if item_group_id:
        #                     product_info['item_group_id'] = int(item_group_id)
        #                     print(f"✅ Found ItemGroupId via ProductRealtime API: {item_group_id}")
        #                 else:
        #                     print(f"⚠️ ItemGroupId not found in ProductRealtime API response")

        #                 if subcategory_id:
        #                     product_info['subcategory_id'] = str(subcategory_id)
        #                     print(f"✅ Found SubCategoryId via ProductRealtime API: {subcategory_id}")
        #                 else:
        #                     print(f"⚠️ SubCategoryId not found in ProductRealtime API response")
        #                     product_info['subcategory_id'] = "3743"  # Default fallback

        #                 # Print first 500 chars of response for debugging
        #                 print(f"📄 API Response preview: {str(realtime_data)[:500]}...")

        #             else:
        #                 print(f"⚠️ ProductRealtime API returned non-dict response")
        #                 product_info['subcategory_id'] = "3743"  # Default fallback

        #         except json.JSONDecodeError as e:
        #             print(f"⚠️ ProductRealtime API returned invalid JSON: {e}")
        #             print(f"📄 Raw response: {response.text[:200]}...")
        #             product_info['subcategory_id'] = "3743"  # Default fallback

        #     else:
        #         print(f"⚠️ ProductRealtime API failed with status {response.status_code}")
        #         print(f"📄 Response: {response.text[:200]}...")
        #         product_info['subcategory_id'] = "3743"  # Default fallback

        # except Exception as e:
        #     print(f"⚠️ Could not call ProductRealtime API: {e}")
        #     product_info['subcategory_id'] = "3743"  # Default fallback

        # Print final extracted values for debugging
        # print(f"\n🔍 FINAL EXTRACTED VALUES:")
        # print(f"📦 Product Info Summary:")
        # print(f"   NeweggItemNumber: {product_info['newegg_item_number']}")
        # print(f"   ItemNumber: {product_info['item_number']}")
        # print(f"   ItemGroupId: {product_info.get('item_group_id', 'NOT FOUND')}")
        # print(f"   SubCategoryId: {product_info.get('subcategory_id', 'NOT FOUND')}")
        # print()

        # Set referer header
        self.session.headers['referer'] = product_url

        # Wait a bit before API calls
        import time
        print("⏳ Waiting before API calls...")
        time.sleep(1)

        all_reviews = []
        total_reviews = 0

        for page in range(1, max_pages + 1):
            print(f"\n📄 Fetching page {page}...")

            api_url = self.build_review_api_url(product_info, page_index=page)

            try:
                print(f"🌐 API URL: {api_url[:100]}...")

                # Print the full curl equivalent request for debugging
                #self.print_curl_equivalent(api_url)

                # Call the API exactly like we call HTML pages - no special headers or treatment
                # Just use the session as-is, the same way HTML fetching works
                print(f"🔄 Calling reviews API like a regular page request...")

                # Debug session state before API call
                self._debug_session_state("BEFORE_API_CALL")

                response = self.session.get(api_url, timeout=15)

                print(f"📊 API Response Status: {response.status_code}")
                print(f"📊 Response Content-Type: {response.headers.get('content-type', 'Unknown')}")
                print(f"📊 Response Size: {len(response.content)} bytes")

                # Debug: Print first 200 chars of response for troubleshooting
                response_preview = response.text[:200].replace('\n', '\\n').replace('\r', '\\r')
                print(f"📄 Response Preview: {response_preview}")

                if response.status_code == 403:
                    print(f"🔒 403 Forbidden - API access denied")
                    print(f"💡 This might be due to:")
                    print(f"   - Missing or invalid cookies")
                    print(f"   - Incorrect item number format")
                    print(f"   - Rate limiting")
                    print(f"   - Missing required headers")

                    # Try to extract item group ID from product page HTML as fallback
                    print(f"🔄 Attempting to extract item group ID from product page...")
                    try:
                        product_response = self.session.get(product_url, timeout=10)
                        if product_response.status_code == 200:
                            import re
                            # Look for ItemGroupId in the HTML
                            group_id_match = re.search(r'"ItemGroupId"\s*:\s*(\d+)', product_response.text)
                            if group_id_match:
                                item_group_id = int(group_id_match.group(1))
                                product_info['item_group_id'] = item_group_id
                                print(f"✅ Found ItemGroupId: {item_group_id}")

                                # Retry with correct group ID
                                api_url = self.build_review_api_url(product_info, page_index=page)
                                print(f"🔄 Retrying with ItemGroupId...")
                                response = self.session.get(api_url, timeout=15)
                                print(f"📊 Retry Response Status: {response.status_code}")
                    except Exception as e:
                        print(f"⚠️ Could not extract ItemGroupId: {e}")

                data = response.json()

                # Debug: Show what we got from the API
                print(f"📊 API Response keys: {list(data.keys())}")
                print(f"📊 Response data structure:")
                for key, value in data.items():
                    if isinstance(value, list):
                        print(f"   {key}: list with {len(value)} items")
                    elif isinstance(value, dict):
                        print(f"   {key}: dict with keys {list(value.keys())}")
                    else:
                        print(f"   {key}: {type(value).__name__} = {value}")

                # Extract ItemGroupId from the API response if we don't have it yet
                if not product_info.get('item_group_id') and 'SearchResult' in data:
                    search_result = data['SearchResult']
                    if 'ReivewFilter' in search_result:  # Note: Newegg's typo
                        review_filter = search_result['ReivewFilter']
                        if 'ItemGroupID' in review_filter:
                            extracted_group_id = review_filter['ItemGroupID']
                            product_info['item_group_id'] = extracted_group_id
                            print(f"✅ Extracted ItemGroupId from API response: {extracted_group_id}")

                            # Now retry the API call with the correct ItemGroupId
                            print(f"🔄 Retrying API call with extracted ItemGroupId...")
                            api_url = self.build_review_api_url(product_info, page_index=page)
                            response = self.session.get(api_url, timeout=15)
                            print(f"📊 Retry API Response Status: {response.status_code}")
                            if response.status_code == 200:
                                data = response.json()
                                print(f"✅ Retry successful with extracted ItemGroupId")

                response.raise_for_status()

                # Print the full response for debugging
                # print(f"\n📄 FULL API RESPONSE:")
                # print(f"{json.dumps(data, indent=2)[:2000]}...")  # First 2000 chars

                # Try different possible keys for reviews
                reviews_data = None

                # Check in SearchResult first (based on the structure we saw)
                if 'SearchResult' in data and data['SearchResult']:
                    search_result = data['SearchResult']
                    if 'CustomerReviewList' in search_result and search_result['CustomerReviewList']:
                        reviews_data = search_result['CustomerReviewList']
                        print(f"✅ Found reviews in SearchResult->CustomerReviewList with {len(reviews_data)} items")

                # Fallback to other possible locations
                if not reviews_data:
                    review_keys = ['ReviewList', 'Reviews', 'reviewList', 'reviews', 'ReviewData']
                    for key in review_keys:
                        if key in data and data[key]:
                            reviews_data = data[key]
                            print(f"✅ Found reviews in '{key}' with {len(reviews_data)} items")
                            break

                if reviews_data:
                    page_reviews = []

                    for review_item in reviews_data:
                        review = self.parse_review(review_item)
                        if review:
                            page_reviews.append(review)

                    all_reviews.extend(page_reviews)
                    print(f"✅ Extracted {len(page_reviews)} reviews from page {page}")

                    # Get total review count from first page
                    if page == 1:
                        # First check in SearchResult
                        if 'SearchResult' in data and 'TotalRecordCount' in data['SearchResult']:
                            total_reviews = data['SearchResult']['TotalRecordCount']
                            print(f"📊 Total reviews available: {total_reviews} (from SearchResult->TotalRecordCount)")
                        else:
                            # Fallback to other keys
                            total_keys = ['TotalReviewCount', 'TotalCount', 'totalReviewCount', 'ReviewCount']
                            for key in total_keys:
                                if key in data:
                                    total_reviews = data[key]
                                    print(f"📊 Total reviews available: {total_reviews} (from {key})")
                                    break

                else:
                    print(f"⚠️ No reviews found on page {page}")
                    # Don't break immediately - maybe other pages have reviews
                    if page == 1:
                        print(f"💡 No reviews on first page - this product might not have any reviews yet")
                        break

            except Exception as e:
                print(f"❌ Error fetching page {page}: {e}")
                break

        return {
            'product_info': product_info,
            'reviews': [asdict(review) for review in all_reviews],
            'total_reviews_extracted': len(all_reviews),
            'total_reviews_available': total_reviews
        }

    def parse_review(self, review_data: dict) -> Optional[Review]:
        """Parse individual review from API response"""
        try:
            # Extract reviewer name - use DisplayName first, then NickName, then Anonymous
            reviewer_name = review_data.get('DisplayName') or review_data.get('NickName', 'Anonymous')

            # Extract rating
            rating = str(review_data.get('Rating', 0))

            # Extract title and comments
            title = review_data.get('Title', '').strip()
            comments = review_data.get('Comments', '').strip()

            # Extract date - format from "2024-09-21T13:14:08.03" to "2024-09-21"
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
            print(f"⚠️ Error parsing review: {e}")
            return None

def main():
    print("🔍 NEWEGG REVIEWS FETCHER")
    print("=" * 50)

    # Get product URL from command line or use default
    if len(sys.argv) > 1:
        product_url = sys.argv[1]
        print(f"🔗 Using provided URL: {product_url}")
    # else:
    #     product_url = "https://www.newegg.com/asus-vy249hgr-27-fhd-120-hz-ips-black/p/N82E16824281334"
    #     print(f"🔗 Using default URL: {product_url}")
    print()

    fetcher = NeweggReviewsFetcher()

    try:
        reviews_data = fetcher.fetch_reviews(product_url, max_pages=2)

        if reviews_data['reviews']:
            print(f"\n🎉 SUCCESS! Extracted {reviews_data['total_reviews_extracted']} reviews")

            # Save to JSON
            with open('newegg_reviews_api.json', 'w', encoding='utf-8') as f:
                json.dump(reviews_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Reviews saved to newegg_reviews_api.json")

            # Show sample reviews
            print(f"\n💬 SAMPLE REVIEWS:")
            for i, review in enumerate(reviews_data['reviews'][:3], 1):
                print(f"\n--- Review {i} ---")
                print(f"👤 Reviewer: {review['reviewer_name']}")
                print(f"⭐ Rating: {review['rating']}/5")
                print(f"📋 Title: {review['review_title']}")
                print(f"💭 Body: {review['review_body'][:150]}...")
                print(f"📅 Date: {review['date']}")
                print(f"✅ Verified Buyer: {review['verified_buyer']}")
                if review.get('pros'):
                    print(f"👍 Pros: {review['pros']}")
                if review.get('cons'):
                    print(f"👎 Cons: {review['cons']}")
                if review.get('helpful_count'):
                    print(f"🤝 Helpful: {review['helpful_count']} people")
                if review.get('brand'):
                    print(f"🏷️  Brand: {review['brand']}")
                if review.get('vendor_reply'):
                    print(f"🔄 Vendor Reply: {review['vendor_reply']}")
                if review.get('purchase_mark'):
                    print(f"🛒 Purchase Mark: {review['purchase_mark']}")
                if review.get('total_voting'):
                    print(f"🗳️  Total Votes: {review['total_voting']}")
        else:
            print("❌ No reviews extracted")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()