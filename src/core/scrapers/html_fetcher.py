#!/usr/bin/env python3
"""
Simple HTML Fetcher for Newegg
ONLY fetches HTML and saves it - no data extraction
"""

import requests
from bs4 import BeautifulSoup
import time
import random
import re

try:
    from fake_useragent import UserAgent
    FAKE_USERAGENT_AVAILABLE = True
except ImportError:
    FAKE_USERAGENT_AVAILABLE = False
    print("⚠️  fake-useragent not installed. Install with: pip install fake-useragent")

class SimpleNeweggFetcher:
    def __init__(self):
        self.session = requests.Session()

        # Initialize fake user agent if available
        if FAKE_USERAGENT_AVAILABLE:
            self.ua = UserAgent()
            print("✅ Using fake-useragent for realistic user agents")
        else:
            # Fallback to static DESKTOP user agents
            self.user_agents = [
                # Chrome Desktop
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                # Firefox Desktop
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
                'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
                # Safari Desktop
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',
            ]
            print("⚠️  Using fallback static DESKTOP user agents")

        self.max_retries = 3
        self.base_delay = 2
        self.setup_session()

    def get_session(self):
        """Return the session for reuse"""
        return self.session

    def setup_session(self):
        """Setup session with random user agent and headers"""
        user_agent = self.get_random_user_agent()

        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',  # Indicates user-initiated navigation
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Viewport-Width': '1920',  # Desktop viewport width
            'sec-ch-ua-platform': '"Windows"',  # Hint that it's desktop
        })
        print(f"🕵️  Using User-Agent: {user_agent[:50]}...")

    def get_random_user_agent(self):
        """Get a random DESKTOP user agent using fake-useragent or fallback"""
        if FAKE_USERAGENT_AVAILABLE:
            try:
                # Get multiple user agents and filter for desktop only
                max_attempts = 10
                for _ in range(max_attempts):
                    # Try different browser types randomly
                    browsers = ['chrome', 'firefox', 'safari']  # Removed 'edge' as it's less reliable
                    browser = random.choice(browsers)

                    if browser == 'chrome':
                        ua = self.ua.chrome
                    elif browser == 'firefox':
                        ua = self.ua.firefox
                    elif browser == 'safari':
                        ua = self.ua.safari
                    else:
                        ua = self.ua.random

                    # Filter out mobile user agents
                    mobile_indicators = [
                        'mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry',
                        'windows phone', 'palm', 'symbian', 'kindle', 'silk', 'opera mini'
                    ]

                    ua_lower = ua.lower()
                    is_mobile = any(indicator in ua_lower for indicator in mobile_indicators)

                    if not is_mobile:
                        print(f"🖥️  Selected desktop user agent: {browser}")
                        return ua

                # If all attempts yielded mobile UAs, fall back to our static desktop UAs
                print("⚠️  All fake-useragent attempts were mobile. Using fallback desktop UA.")
                return random.choice(self.user_agents)

            except Exception as e:
                print(f"⚠️  fake-useragent failed: {e}. Using fallback.")
                return random.choice(self.user_agents)
        else:
            return random.choice(self.user_agents)

    def establish_session(self):
        """Establish session by visiting main Newegg page first"""
        try:
            print("Establishing session with Newegg...")
            main_page = "https://www.newegg.com"
            response = self.session.get(main_page, timeout=10)
            if response.status_code == 200:
                print("Session established successfully")
                time.sleep(random.uniform(1, 3))
                return True
            else:
                print("Failed to establish session")
                return False
        except Exception as e:
            print(f"Error establishing session: {e}")
            return False

    def fetch_html(self, url: str) -> bool:
        """Fetch HTML and save it - returns True if successful"""

        # First establish session by visiting main Newegg page
        if not self.establish_session():
            print(" Proceeding without session establishment...")

        for attempt in range(1, self.max_retries + 1):
            try:
                print(f" Attempt {attempt}/{self.max_retries}: Fetching {url}")

                # Random delay before request
                delay = self.base_delay + random.uniform(0, 2)
                time.sleep(delay)

                # Randomize user agent for each attempt
                new_user_agent = self.get_random_user_agent()
                self.session.headers['User-Agent'] = new_user_agent
                print(f" Attempt {attempt}: Using User-Agent: {new_user_agent[:50]}...")

                response = self.session.get(url, timeout=15)
                response.raise_for_status()

                # Check if we got blocked - improved detection
                page_text = response.text.lower()

                # Check for Newegg's specific bot detection page
                is_human_check = "are you a human?" in page_text
                has_recaptcha = "recaptcha" in page_text and "areyouahuman" in page_text

                	
                other_blocked_keywords = [
                    "access denied",
                    "blocked by cloudflare",
                    "please verify you are human",
                    "captcha verification",
                    "security check required",
                    "temporarily blocked",
                    "rate limit exceeded",
                    "too many requests"
                ]

                has_other_blocked_content = any(keyword in page_text for keyword in other_blocked_keywords)

                # Strong positive indicators of a successful Newegg product page
                success_indicators = [
                    "product-title",
                    "price-current",
                    "add to cart",
                    "product-wrap",
                    "__initialstate__",
                    "item-rating-num",
                    "product-main",
                    "rating rating-", 
                    "item-container"
                ]

                has_success_content = any(indicator in page_text for indicator in success_indicators)
                is_actually_blocked = is_human_check or has_recaptcha or (has_other_blocked_content and not has_success_content)

                print(f"    Page analysis:")
                print(f"  - Human check page: {is_human_check}")
                print(f"  - Has reCAPTCHA: {has_recaptcha}")
                print(f"  - Success content: {has_success_content}")
                print(f"  - Actually blocked: {is_actually_blocked}")

                # If we have clear success indicators, save and return
                if has_success_content and not is_actually_blocked:
                    print(f" Valid product page detected on attempt {attempt}")

                    # Save successful response for manual review
                    success_filename = f'successful_response_attempt_{attempt}.html'
                    try:
                        with open(success_filename, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f" Successful response saved to {success_filename}")
                        return True
                    except Exception as e:
                        print(f"⚠️ Could not save successful response: {e}")
                        return False

                if is_actually_blocked:
                    if is_human_check:
                        print(f" Newegg 'Are you a human?' page detected on attempt {attempt}")
                    elif has_recaptcha:
                        print(f" reCAPTCHA challenge detected on attempt {attempt}")

                    print(f"Response length: {len(response.text)}")

                    # Save response for debugging
                    debug_filename = f'debug_response_attempt_{attempt}.html'
                    with open(debug_filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"Response saved to {debug_filename}")

                    if attempt < self.max_retries:
                        # Exponential backoff with jitter
                        retry_delay = (2 ** attempt) + random.uniform(1, 5)
                        print(f"Retrying in {retry_delay:.1f} seconds...")
                        time.sleep(retry_delay)

                        # Create new session for retry
                        self.session.close()
                        self.session = requests.Session()
                        self.setup_session()
                        continue
                    else:
                        print(" Max retries exceeded. Bot detection persists.")
                        return False

                # Final check - if we reach here without success indicators, it might still be a problem
                if not has_success_content:
                    print(f"  Page fetched but no product content detected on attempt {attempt}")

                    # Save this questionable response for inspection
                    questionable_filename = f'questionable_response_attempt_{attempt}.html'
                    try:
                        with open(questionable_filename, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f" Questionable response saved to {questionable_filename}")
                    except Exception as e:
                        print(f"Could not save questionable response: {e}")

                    # Continue to next attempt if we have retries left
                    if attempt < self.max_retries:
                        print(f"Will retry since no product content was detected...")
                        continue

                print(f" Page fetched successfully on attempt {attempt}")

                # Save final response
                final_filename = f'final_response_attempt_{attempt}.html'
                try:
                    with open(final_filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f" Final response saved to {final_filename}")
                    return True
                except Exception as e:
                    print(f"  Could not save final response: {e}")
                    return False

            except requests.exceptions.RequestException as e:
                print(f"Request error on attempt {attempt}: {e}")
                if attempt < self.max_retries:
                    retry_delay = (2 ** attempt) + random.uniform(1, 3)
                    print(f"Retrying in {retry_delay:.1f} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(" Max retries exceeded due to request errors.")
                    return False
            except Exception as e:
                print(f"Unexpected error on attempt {attempt}: {e}")
                if attempt < self.max_retries:
                    time.sleep(2)
                    continue
                else:
                    return False

        return False

# def main():
#     print("🚀 SIMPLE NEWEGG HTML FETCHER")
#     print("=" * 40)
#     print("This script ONLY fetches HTML - no data extraction!")
#     print()

#     # URL to scrape
#     url = "https://www.newegg.com/p/N82E16868105274"

#     fetcher = SimpleNeweggFetcher()
#     success = fetcher.fetch_html(url)

#     if success:
#         print("\n✅ HTML FETCH COMPLETED SUCCESSFULLY!")
#         print("📁 Check the saved HTML files for the fetched content.")
#     else:
#         print("\n❌ HTML FETCH FAILED!")
#         print("📁 Check debug files for troubleshooting.")

# if __name__ == "__main__":
#     main()