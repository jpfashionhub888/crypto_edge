# data/crypto_fetcher.py
# CRYPTOEDGE - Crypto Data Fetcher
# Uses CCXT to fetch from Coinbase
# Falls back to yfinance if needed

import ccxt
import pandas as pd
import numpy as np
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CryptoDataFetcher:
    """
    Fetches OHLCV data for crypto pairs.
    Primary: Coinbase via CCXT
    Fallback: yfinance
    """

    def __init__(self):
        try:
            self.exchange = ccxt.coinbase({
                'rateLimit'       : 1200,
                'enableRateLimit' : True,
            })
            print("   Coinbase exchange connected ✅")
        except Exception as e:
            self.exchange = None
            print(f"   Coinbase connection failed: {e}")

    def fetch_ohlcv(self, symbol, days=365):
        """
        Fetch OHLCV data for a crypto pair.
        Returns DataFrame with OHLCV columns.
        """
        # Try CCXT first
        df = self._fetch_ccxt(symbol, days)

        # Fallback to yfinance
        if df is None or df.empty:
            df = self._fetch_yfinance(symbol, days)

        return df

    def _fetch_ccxt(self, symbol, days=365):
        """Fetch via CCXT/Coinbase."""
        if not self.exchange:
            return None

        try:
            since = self.exchange.parse8601(
                (datetime.now() - timedelta(days=days))
                .strftime('%Y-%m-%dT00:00:00Z')
            )

            ohlcv = self.exchange.fetch_ohlcv(
                symbol, '1d', since=since, limit=days
            )

            if not ohlcv:
                return None

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df.index = df.index.tz_localize(None)

            print(f"   {symbol}: {len(df)} rows (Coinbase) ✅")
            return df

        except Exception as e:
            logger.warning(f"CCXT fetch failed for {symbol}: {e}")
            return None

    def _fetch_yfinance(self, symbol, days=365):
        """Fallback: fetch via yfinance."""
        try:
            import yfinance as yf

            # Convert CCXT format to yfinance format
            yf_symbol = symbol.replace('/', '-').replace('USDT', 'USD')

            ticker = yf.Ticker(yf_symbol)
            df     = ticker.history(period=f'{days}d')

            if df.empty:
                return None

            df.columns = [c.lower() for c in df.columns]
            df.index   = df.index.tz_localize(None)
            df         = df[['open', 'high', 'low', 'close', 'volume']]
            df.dropna(inplace=True)

            print(f"   {symbol}: {len(df)} rows (yfinance) ✅")
            return df

        except Exception as e:
            logger.warning(f"yfinance fetch failed for {symbol}: {e}")
            return None

    def fetch_all(self, pairs, days=365):
        """Fetch data for all crypto pairs."""
        print(f"\n   Fetching {len(pairs)} crypto pairs...")
        data = {}

        for symbol in pairs:
            try:
                df = self.fetch_ohlcv(symbol, days)
                if df is not None and len(df) >= 30:
                    data[symbol] = df
                else:
                    print(f"   {symbol}: Insufficient data ❌")
            except Exception as e:
                print(f"   {symbol}: Error - {e} ❌")

        print(f"\n   Fetched {len(data)}/{len(pairs)} pairs")
        return data

    def get_fear_greed_index(self):
        """
        Fetch Fear & Greed Index from alternative.me
        Returns score 0-100 and classification
        """
        try:
            response = requests.get(
                'https://api.alternative.me/fng/',
                timeout=10
            )
            data  = response.json()
            value = int(data['data'][0]['value'])
            label = data['data'][0]['value_classification']

            print(f"   Fear & Greed Index: {value} ({label})")
            return value, label

        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")
            return 50, 'Neutral'

    def get_bitcoin_dominance(self):
        """
        Fetch Bitcoin dominance from CoinGecko.
        High dominance = sell altcoins
        Low dominance = buy altcoins
        """
        try:
            response = requests.get(
                'https://api.coingecko.com/api/v3/global',
                timeout=10
            )
            data = response.json()
            btc_dominance = data['data']['market_cap_percentage']['btc']

            print(f"   BTC Dominance: {btc_dominance:.1f}%")
            return btc_dominance

        except Exception as e:
            logger.warning(f"BTC dominance fetch failed: {e}")
            return 50.0


if __name__ == '__main__':
    print("\nTesting CryptoEdge Data Fetcher...")
    fetcher = CryptoDataFetcher()

    # Test Fear & Greed
    fg_value, fg_label = fetcher.get_fear_greed_index()
    print(f"Fear & Greed: {fg_value} - {fg_label}")

    # Test BTC Dominance
    btc_dom = fetcher.get_bitcoin_dominance()
    print(f"BTC Dominance: {btc_dom:.1f}%")

    # Test data fetch
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    data  = fetcher.fetch_all(pairs, days=30)
    print(f"\nFetched {len(data)} pairs successfully!")