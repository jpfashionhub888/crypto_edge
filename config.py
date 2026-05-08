# config.py
# CRYPTOEDGE - Configuration

import os
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# CRYPTO PAIRS TO TRADE
# ==========================================
CRYPTO_PAIRS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'ADA/USDT',
    'AVAX/USDT',
    'POL/USDT',
    'LINK/USDT',
    'DOT/USDT',
    'LTC/USDT',
]

# ==========================================
# EXCHANGE SETTINGS
# ==========================================
EXCHANGE          = 'coinbase'
COINBASE_API_KEY  = os.getenv('COINBASE_API_KEY', '')
COINBASE_SECRET   = os.getenv('COINBASE_SECRET', '')

# ==========================================
# PAPER TRADING SETTINGS
# ==========================================
STARTING_CAPITAL  = 10000.0  # $10,000 USDT
MAX_POSITIONS     = 5
MAX_POSITION_PCT  = 0.20     # 20% per position
STOP_LOSS_PCT     = 0.05     # 5% stop loss
TAKE_PROFIT_PCT   = 0.15     # 15% take profit
TRAILING_STOP_PCT = 0.04     # 4% trailing stop

# ==========================================
# ML MODEL SETTINGS
# ==========================================
LOOKBACK_DAYS     = 365      # 1 year of data
TRAIN_DAYS        = 180      # 6 month training window
PREDICTION_THRESHOLD = 0.60  # Min confidence to trade

# ==========================================
# TELEGRAM SETTINGS
# ==========================================
TELEGRAM_TOKEN    = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID  = os.getenv('TELEGRAM_CHAT_ID', '')

# ==========================================
# GROQ AI SETTINGS
# ==========================================
GROQ_API_KEY      = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL        = 'llama-3.3-70b-versatile'

# ==========================================
# FEAR & GREED INDEX
# ==========================================
FEAR_GREED_URL    = 'https://api.alternative.me/fng/'

# ==========================================
# CRYPTO SPECIFIC RISK
# ==========================================
# Crypto is more volatile than stocks
# So we use wider stops
CRYPTO_STOP_LOSS      = 0.05   # 5% (vs 3% for stocks)
CRYPTO_TAKE_PROFIT    = 0.15   # 15% (vs 8% for stocks)
CRYPTO_TRAILING_STOP  = 0.04   # 4% (vs 2.5% for stocks)