"""
Exness Gold Price Scraper using Playwright
Lấy giá XAU/USD realtime từ Exness bằng Playwright (headless browser)
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional
import re

try:
    from playwright.async_api import async_playwright
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. pip install playwright && playwright install chromium")


class ExnessGoldScraper:
    """
    Scrape giá XAU/USD realtime từ Exness bằng Playwright
    Exness cập nhật giá mỗi ~30 giây
    """
    
    URL = "https://www.exness.com/vi/commodities/xauusd/"
    
    # CSS Selectors
    PRICE_SELECTOR = ".MuiTypography-hero2Adaptive"
    SPREAD_SELECTOR = ".MuiTypography-body4SemiboldAdaptive"
    
    def __init__(self, headless: bool = True):
        """
        Args:
            headless: True = chạy background, False = hiện browser
        """
        self.headless = headless
        self.browser = None
        self.page = None
        self.last_price = None
    
    def get_price_sync(self) -> Dict:
        """
        Lấy giá đồng bộ (blocking)
        Sử dụng cho các trường hợp không cần async
        
        Returns:
            Dict với price, spread, timestamp, source
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {'error': 'Playwright not available'}
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()
                
                # Navigate and wait for page to load
                page.goto(self.URL, wait_until='load', timeout=60000)
                
                # Wait for page to fully render (JavaScript)
                page.wait_for_timeout(5000)
                
                # Try multiple methods to get price
                price = None
                
                # Method 1: Try the MUI selector
                try:
                    price_el = page.query_selector(self.PRICE_SELECTOR)
                    if price_el:
                        price_text = price_el.inner_text()
                        price = self._parse_price(price_text)
                except:
                    pass
                
                # Method 2: Use JavaScript to find price
                if not price:
                    try:
                        js_result = page.evaluate('''() => {
                            // Try finding by class
                            const el = document.querySelector('.MuiTypography-hero2Adaptive');
                            if (el) return el.innerText;
                            
                            // Try finding any large number (price pattern)
                            const allText = document.body.innerText;
                            const match = allText.match(/\\d{4}\\.\\d{2}/g);
                            if (match) return match[0];
                            
                            return null;
                        }''')
                        if js_result:
                            price = self._parse_price(js_result)
                    except:
                        pass
                
                browser.close()
                
                if price:
                    self.last_price = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'exness_playwright'
                    }
                    return self.last_price
                
                return {'error': 'Price not found'}
                
        except Exception as e:
            return {'error': str(e)}
    
    async def get_price_async(self) -> Dict:
        """
        Lấy giá bất đồng bộ (non-blocking)
        Hiệu quả hơn cho high concurrency
        
        Returns:
            Dict với price, spread, timestamp, source
        """
        if not PLAYWRIGHT_AVAILABLE:
            return {'error': 'Playwright not available'}
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                page = await browser.new_page()
                
                # Navigate
                await page.goto(self.URL, wait_until='networkidle', timeout=30000)
                
                # Wait for price element
                await page.wait_for_selector(self.PRICE_SELECTOR, timeout=10000)
                
                # Extract price
                price_el = await page.query_selector(self.PRICE_SELECTOR)
                if price_el:
                    price_text = await price_el.inner_text()
                    price = self._parse_price(price_text)
                    
                    if price:
                        self.last_price = {
                            'price': price,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'exness_playwright'
                        }
                        
                        await browser.close()
                        return self.last_price
                
                await browser.close()
                return {'error': 'Price not found'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price từ text"""
        try:
            # Remove non-numeric characters except .
            clean = re.sub(r'[^\d.]', '', price_text)
            if clean:
                return round(float(clean), 2)
        except:
            pass
        return None
    
    async def stream_prices_async(self, interval_seconds: float = 30, callback=None, duration: int = None):
        """
        Stream giá liên tục (async)
        Mở browser 1 lần và refresh để lấy giá mới
        
        Args:
            interval_seconds: Tần suất lấy giá (Exness update ~30s)
            callback: Async function xử lý giá mới
            duration: Thời gian stream (None = vô hạn)
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("❌ Playwright not available")
            return
        
        print(f"🔴 Starting Exness price stream (interval: {interval_seconds}s)...")
        
        start_time = asyncio.get_event_loop().time()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            # Initial load
            await page.goto(self.URL, wait_until='networkidle', timeout=30000)
            
            while True:
                if duration and (asyncio.get_event_loop().time() - start_time) > duration:
                    print("\n⏹️ Stream duration reached")
                    break
                
                try:
                    # Wait for price element
                    await page.wait_for_selector(self.PRICE_SELECTOR, timeout=10000)
                    
                    # Get price
                    price_el = await page.query_selector(self.PRICE_SELECTOR)
                    if price_el:
                        price_text = await price_el.inner_text()
                        price = self._parse_price(price_text)
                        
                        if price:
                            price_data = {
                                'price': price,
                                'timestamp': datetime.now().isoformat(),
                                'source': 'exness_stream'
                            }
                            self.last_price = price_data
                            
                            if callback:
                                await callback(price_data)
                            else:
                                ts = datetime.now().strftime('%H:%M:%S')
                                print(f"💰 {ts} | XAU/USD: ${price:.2f} (Exness)")
                    
                    # Wait and refresh
                    await asyncio.sleep(interval_seconds)
                    await page.reload(wait_until='networkidle')
                    
                except KeyboardInterrupt:
                    print("\n⏹️ Stream stopped by user")
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    await asyncio.sleep(5)
            
            await browser.close()


def get_exness_price() -> Dict:
    """
    Helper function để lấy giá từ Exness (sync)
    Sử dụng trong code không async
    """
    scraper = ExnessGoldScraper()
    return scraper.get_price_sync()


# Quick test
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 TESTING EXNESS PLAYWRIGHT SCRAPER")
    print("=" * 50)
    
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright not installed!")
        print("   Run: pip install playwright && playwright install chromium")
    else:
        print("\n📡 Fetching price from Exness...")
        
        scraper = ExnessGoldScraper(headless=True)
        result = scraper.get_price_sync()
        
        if result.get('price'):
            print(f"✅ SUCCESS!")
            print(f"   💰 Price: ${result['price']:.2f}")
            print(f"   📊 Source: {result.get('source')}")
            print(f"   ⏰ Time: {result.get('timestamp')}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        # Optional: Test stream for 60 seconds
        # print("\n🔴 Testing stream for 60 seconds...")
        # asyncio.run(scraper.stream_prices_async(interval_seconds=30, duration=60))
    
    print("\n✅ Test completed!")
