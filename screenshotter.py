"""
screenshotter.py - Domain Screenshot Capture Module
Usage: python screenshotter.py
"""

import asyncio
import time
import csv
import os
import random
import sys

# --- Windows asyncio fix for Playwright ---
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


class DomainScreenshotter:
    def __init__(self, output_folder="screenshots", concurrency=2,
                 default_timeout=30000, max_timeout=90000, default_wait=3):
        self.output_folder = output_folder
        self.concurrency = concurrency
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.default_wait = default_wait
        self.results = []
        os.makedirs(output_folder, exist_ok=True)
        
        # Rotate user agents for better success
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]

    async def capture_domain(self, domain, retry_count=1, use_firefox=False):
        if not domain.startswith(('http://', 'https://')):
            urls_to_try = [f"https://{domain}", f"http://{domain}"]
        else:
            urls_to_try = [domain]

        domain_name = domain.replace('https://', '').replace('http://', '').rstrip('/')
        domain_name = domain_name.replace('/', '_').replace(':', '_').replace('www.', '')
        output_path = f"{self.output_folder}/{domain_name}.png"
        current_timeout = min(self.default_timeout * retry_count, self.max_timeout)
        start_time = time.time()
        success = False
        error_msg = None
        
        # Rotate user agent
        user_agent = random.choice(self.user_agents)

        async with async_playwright() as p:
            try:
                # Try Firefox first on retries (less detected)
                browser_type = p.firefox if (use_firefox or retry_count > 1) else p.chromium
                
                # Enhanced browser configuration with anti-detection
                browser = await browser_type.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-web-security',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--window-size=1920,1080',
                        '--disable-infobars',
                        '--disable-extensions'
                    ] if browser_type == p.chromium else []
                )

                # Enhanced context with realistic fingerprint
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=user_agent,
                    color_scheme="light",  # <-- THIS ENSURES light mode
                    locale='en-US',
                    timezone_id='America/New_York',
                    device_scale_factor=1,
                    has_touch=False,
                    java_script_enabled=True,
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0',
                        'DNT': '1'
                    }
                )

                page = await context.new_page()
                
                # Inject anti-detection scripts
                await page.add_init_script("""
                    // Hide webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override the permissions API
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    
                    // Mock plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            {
                                0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                                description: "Portable Document Format",
                                filename: "internal-pdf-viewer",
                                length: 1,
                                name: "Chrome PDF Plugin"
                            }
                        ]
                    });
                    
                    // Mock languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Add chrome object for Chromium
                    if (!window.chrome) {
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                    }
                    
                    // Mock permissions
                    const originalPermissions = navigator.permissions;
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: async (params) => ({
                                state: 'prompt',
                                onchange: null
                            })
                        })
                    });
                """)
                
                page.set_default_navigation_timeout(current_timeout)
                
                # Handle dialogs automatically
                page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))

                # Try different URLs (HTTPS first, then HTTP)
                navigation_success = False
                for url in urls_to_try:
                    try:
                        # Try different wait strategies
                        try:
                            response = await page.goto(url, wait_until='domcontentloaded', timeout=current_timeout)
                            if response and response.status < 400:
                                navigation_success = True
                                break
                        except PlaywrightTimeoutError:
                            # Fallback to 'commit' if domcontentloaded times out
                            await page.goto(url, wait_until='commit', timeout=current_timeout // 2)
                            navigation_success = True
                            break
                    except Exception as e:
                        error_msg = f"Navigation failed: {str(e)}"
                        if url == urls_to_try[-1]:
                            raise

                if navigation_success:
                    # Add random human-like delay
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    
                    # Wait for network to be idle (with timeout)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=self.default_wait * 1000)
                    except PlaywrightTimeoutError:
                        pass  # Continue anyway

                    # Scroll to trigger lazy loading
                    try:
                        await page.evaluate("""
                            async () => {
                                await new Promise((resolve) => {
                                    let totalHeight = 0;
                                    const distance = 100;
                                    const timer = setInterval(() => {
                                        const scrollHeight = document.body.scrollHeight;
                                        window.scrollBy(0, distance);
                                        totalHeight += distance;

                                        if(totalHeight >= scrollHeight){
                                            window.scrollTo(0, 0);
                                            clearInterval(timer);
                                            resolve();
                                        }
                                    }, 100);
                                });
                            }
                        """)
                    except:
                        pass

                    # Small delay after scroll
                    await asyncio.sleep(0.5)

                    # Take screenshot
                    await page.screenshot(path=output_path, full_page=True)
                    success = True
                    print(f"✅ Successfully captured: {domain}")

            except PlaywrightTimeoutError:
                try:
                    # Try to capture partial screenshot
                    await page.screenshot(path=output_path, full_page=False)
                    error_msg = "Partial screenshot (timeout)"
                    success = True
                    print(f"⚠️ Partial capture: {domain}")
                except Exception as e:
                    error_msg = f"Failed to capture: {str(e)}"
                    print(f"❌ Failed: {domain} - {error_msg}")
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                print(f"❌ Error: {domain} - {error_msg}")
            finally:
                try:
                    await browser.close()
                except:
                    pass

        result = {
            "domain": domain,
            "success": success,
            "elapsed_time": round(time.time() - start_time, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timeout_used": current_timeout,
            "browser": "Firefox" if use_firefox or retry_count > 1 else "Chromium",
            "output_path": output_path if success else None,
            "error": error_msg
        }

        # Retry logic with Firefox fallback
        if not success and retry_count < 3:
            print(f"🔄 Retrying {domain} (attempt {retry_count + 1})")
            await asyncio.sleep(random.uniform(3, 6))  # Random delay between retries
            return await self.capture_domain(domain, retry_count + 1, use_firefox=True)

        self.results.append(result)
        return result

    async def run(self, domains):
        """Run screenshot capture with batching and delays"""
        results = []
        total = len(domains)
        
        print(f"\n🚀 Starting capture of {total} domains with concurrency={self.concurrency}\n")
        
        for i in range(0, len(domains), self.concurrency):
            batch = domains[i:i + self.concurrency]
            batch_num = (i // self.concurrency) + 1
            total_batches = (total + self.concurrency - 1) // self.concurrency
            
            print(f"📦 Batch {batch_num}/{total_batches}: Processing {len(batch)} domains...")
            
            batch_results = await asyncio.gather(*[self.capture_domain(d) for d in batch])
            results.extend(batch_results)
            
            # Add random delay between batches to avoid rate limiting
            if i + self.concurrency < len(domains):
                delay = random.uniform(2, 4)
                print(f"⏳ Waiting {delay:.1f}s before next batch...\n")
                await asyncio.sleep(delay)
        
        self.save_results_csv()
        self.print_summary()
        return results

    def save_results_csv(self):
        """Save results to CSV"""
        if self.results:
            csv_path = f"{self.output_folder}/results.csv"
            with open(csv_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
                writer.writeheader()
                writer.writerows(self.results)
            print(f"\n💾 Results saved to {csv_path}")

    def print_summary(self):
        """Print execution summary"""
        if not self.results:
            return
            
        successful = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - successful
        total_time = sum(r['elapsed_time'] for r in self.results)
        
        print(f"\n{'='*50}")
        print(f"📊 SUMMARY")
        print(f"{'='*50}")
        print(f"✅ Successful: {successful}/{len(self.results)}")
        print(f"❌ Failed: {failed}/{len(self.results)}")
        print(f"⏱️  Total time: {total_time:.2f}s")
        print(f"⚡ Avg time/domain: {total_time/len(self.results):.2f}s")
        print(f"{'='*50}\n")


def take_screenshots(domains, output_folder="screenshots", concurrency=2):
    """Convenience function to take screenshots"""
    if isinstance(domains, str):
        domains = [domains]
    screenshotter = DomainScreenshotter(output_folder, concurrency)
    return asyncio.run(screenshotter.run(domains))


# CLI Usage
if __name__ == "__main__":
    # Example domains
    domains = [
        "cricbuzz.com",
        "stackoverflow.com"
    ]
    
    print("="*60)
    print("🚀 DOMAIN SCREENSHOTTER")
    print("="*60)
    
    take_screenshots(domains)
