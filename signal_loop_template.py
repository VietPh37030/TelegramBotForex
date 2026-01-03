"""
Fast signal monitoring loop - runs in separate thread
"""

def run_signal_loop(self):
    """
    ⚡ FAST LOOP - Real-time Signal & News Monitoring
    Runs every 2-5 minutes to catch trading signals quickly
    """
    print("\n🚀 Starting FAST signal monitoring loop...")
    print(f"   📡 Signal check: every {SIGNAL_CHECK_INTERVAL}s ({SIGNAL_CHECK_INTERVAL//60} min)")
    print(f"   📰 News check: every {NEWS_CHECK_INTERVAL}s ({NEWS_CHECK_INTERVAL//60} min)")
    
    last_signal_check = datetime.now()
    last_news_check = datetime.now()
    iteration = 0
    
    while True:
        try:
            iteration += 1
            now = datetime.now()
            
            # Check if paused
            if self.telegram.is_paused:
                time.sleep(30)  # Short sleep when paused
                continue
            
            # 📡 CHECK SIGNALS (every 2 minutes)
            if (now - last_signal_check).total_seconds() >= SIGNAL_CHECK_INTERVAL:
                print(f"\n⚡ Fast check #{iteration} | {now.strftime('%H:%M:%S')}")
                print("📡 Checking signals from Telegram channels...")
                
                new_signals = self.check_external_signals()
                
                if new_signals > 0:
                    print(f"✅ Found {new_signals} new signals!")
                else:
                    print("📭 No new signals")
                
                last_signal_check = now
            
            # 📰 CHECK NEWS (every 5 minutes)
            if (now - last_news_check).total_seconds() >= NEWS_CHECK_INTERVAL:
                print("📰 Checking news updates...")
                
                news_count = self.check_news_updates()
                
                if news_count > 0:
                    print(f"✅ Found {news_count} new important news!")
                else:
                    print("📭 No new important news")
                
                last_news_check = now
            
            # Sleep for 30s between checks
            time.sleep(30)
            
        except Exception as e:
            print(f"❌ Signal loop error: {e}")
            time.sleep(60)  # Wait 1 min on error
