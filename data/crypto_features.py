# data/crypto_features.py
# CRYPTOEDGE - Crypto Feature Engineering
# Technical indicators + Crypto-specific features

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class CryptoFeatureEngine:
    """
    Builds features for crypto ML models.
    Includes standard technical indicators
    plus crypto-specific features.
    """

    def add_features(self, df, fear_greed=50, btc_dominance=50):
        """Add all features to OHLCV dataframe."""
        df = df.copy()

        try:
            # ── Price Features ─────────────────────────
            df['returns']      = df['close'].pct_change()
            df['log_returns']  = np.log(df['close'] / df['close'].shift(1))
            df['volatility']   = df['returns'].rolling(14).std()
            df['price_range']  = (df['high'] - df['low']) / df['close']

            # ── Moving Averages ─────────────────────────
            df['sma_7']   = df['close'].rolling(7).mean()
            df['sma_14']  = df['close'].rolling(14).mean()
            df['sma_30']  = df['close'].rolling(30).mean()
            df['sma_50']  = df['close'].rolling(50).mean()
            df['ema_12']  = df['close'].ewm(span=12).mean()
            df['ema_26']  = df['close'].ewm(span=26).mean()

            # Price vs MAs
            df['price_vs_sma7']  = df['close'] / df['sma_7'] - 1
            df['price_vs_sma30'] = df['close'] / df['sma_30'] - 1
            df['price_vs_sma50'] = df['close'] / df['sma_50'] - 1
            df['sma7_vs_sma30']  = df['sma_7'] / df['sma_30'] - 1

            # ── MACD ────────────────────────────────────
            df['macd']        = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9).mean()
            df['macd_hist']   = df['macd'] - df['macd_signal']

            # ── RSI ─────────────────────────────────────
            delta    = df['close'].diff()
            gain     = delta.clip(lower=0)
            loss     = -delta.clip(upper=0)
            avg_gain = gain.ewm(span=14).mean()
            avg_loss = loss.ewm(span=14).mean()
            rs       = avg_gain / avg_loss.replace(0, 1)
            df['rsi'] = 100 - (100 / (1 + rs))
            df['rsi_7']  = 100 - (100 / (1 + df['close'].diff().clip(lower=0).ewm(span=7).mean() /
                                          (-df['close'].diff().clip(upper=0)).ewm(span=7).mean().replace(0, 1)))

            # ── Bollinger Bands ──────────────────────────
            bb_mid         = df['close'].rolling(20).mean()
            bb_std         = df['close'].rolling(20).std()
            df['bb_upper'] = bb_mid + 2 * bb_std
            df['bb_lower'] = bb_mid - 2 * bb_std
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / bb_mid
            df['bb_pct']   = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)

            # ── ATR ─────────────────────────────────────
            tr1       = df['high'] - df['low']
            tr2       = abs(df['high'] - df['close'].shift(1))
            tr3       = abs(df['low'] - df['close'].shift(1))
            true_range= pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df['atr'] = true_range.rolling(14).mean()
            df['atr_pct'] = df['atr'] / df['close']

            # ── Volume Features ──────────────────────────
            df['volume_sma']    = df['volume'].rolling(14).mean()
            df['volume_ratio']  = df['volume'] / df['volume_sma']
            df['volume_trend']  = df['volume'].rolling(7).mean() / df['volume'].rolling(14).mean()

            # ── Momentum ────────────────────────────────
            df['mom_3']  = df['close'].pct_change(3)
            df['mom_7']  = df['close'].pct_change(7)
            df['mom_14'] = df['close'].pct_change(14)
            df['mom_30'] = df['close'].pct_change(30)

            # ── Crypto Specific Features ─────────────────
            df['fear_greed']     = fear_greed / 100.0
            df['btc_dominance']  = btc_dominance / 100.0

            # Fear & Greed signals
            df['extreme_fear']   = 1 if fear_greed < 20 else 0
            df['extreme_greed']  = 1 if fear_greed > 80 else 0
            df['fear_zone']      = 1 if fear_greed < 40 else 0
            df['greed_zone']     = 1 if fear_greed > 60 else 0

            # ── Target Variable ──────────────────────────
            future_return    = df['close'].shift(-1) / df['close'] - 1
            df['target']     = (future_return > 0).astype(int)

            # Drop NaN rows
            df.dropna(inplace=True)

        except Exception as e:
            logger.error(f"Feature engineering failed: {e}")

        return df

    def get_feature_names(self):
        """Return list of feature names."""
        return [
            'returns', 'log_returns', 'volatility', 'price_range',
            'price_vs_sma7', 'price_vs_sma30', 'price_vs_sma50',
            'sma7_vs_sma30',
            'macd', 'macd_signal', 'macd_hist',
            'rsi', 'rsi_7',
            'bb_width', 'bb_pct',
            'atr_pct',
            'volume_ratio', 'volume_trend',
            'mom_3', 'mom_7', 'mom_14', 'mom_30',
            'fear_greed', 'btc_dominance',
            'extreme_fear', 'extreme_greed',
            'fear_zone', 'greed_zone',
        ]


if __name__ == '__main__':
    import yfinance as yf
    print("\nTesting CryptoEdge Feature Engine...")

    ticker = yf.Ticker('BTC-USD')
    df     = ticker.history(period='1y')
    df.columns = [c.lower() for c in df.columns]
    df.index   = df.index.tz_localize(None)

    engine   = CryptoFeatureEngine()
    df_feats = engine.add_features(df, fear_greed=38, btc_dominance=58.2)

    features = engine.get_feature_names()
    print(f"\nFeatures generated: {len(features)}")
    print(f"Data rows: {len(df_feats)}")
    print(f"\nSample features:")
    print(df_feats[features].tail(3))