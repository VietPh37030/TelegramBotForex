"""
Services Package - Wyckoff Smart Bot v2.0
"""

# Core modules
from .scraper import RealtimeGoldScraper, DataFetcher
from .indicators import calculate_indicators, get_indicator_summary
from .patterns import detect_patterns, get_pattern_summary

# Wyckoff & SMC
from .wyckoff import WyckoffAnalyzer, WyckoffEvent
from .smc import SMCAnalyzer, SMCZone

# AI & Communication
from .ai_engine import WyckoffAIEngine, AIAnalyst
from .telegram_bot import TelegramCommandBot
from .news_crawler import NewsCrawler

# Risk & Storage
from .risk_manager import RiskManager
from .firebase_service import FirebaseService


__all__ = [
    # Core
    'RealtimeGoldScraper',
    'DataFetcher',
    'calculate_indicators',
    'get_indicator_summary',
    'detect_patterns',
    'get_pattern_summary',
    
    # Wyckoff & SMC
    'WyckoffAnalyzer',
    'WyckoffEvent',
    'SMCAnalyzer',
    'SMCZone',
    
    # AI & Comms
    'WyckoffAIEngine',
    'AIAnalyst',
    'TelegramCommandBot',
    'NewsCrawler',
    
    # Risk & Storage
    'RiskManager',
    'FirebaseService',
]
