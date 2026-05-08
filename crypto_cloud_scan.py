# crypto_cloud_scan.py
# CRYPTOEDGE - Main Cloud Scanner
# Runs on GitHub Actions every 4 hours
# 24/7/365 crypto market coverage

import os
import sys
import warnings
import logging
import json
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'

logging.basicConfig(
    level  = logging.INFO,
    format = '%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    CRYPTO_PAIRS, PREDICTION_THRESHOLD,
    STARTING_CAPITAL, GROQ_API_KEY,
)


def run_crypto_scan():
    """Run complete CryptoEdge scan."""

    now = datetime.now()
    print("\n" + "="*60)
    print(f"CRYPTOEDGE SCAN - {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*60)

    from data.crypto_fetcher   import CryptoDataFetcher
    from data.crypto_features  import CryptoFeatureEngine
    from models.crypto_model   import CryptoEnsemble
    from execution.crypto_paper_trader import CryptoPaperTrader
    from monitoring.crypto_telegram    import CryptoTelegram

    # Initialize components
    fetcher  = CryptoDataFetcher()
    engine   = CryptoFeatureEngine()
    trader   = CryptoPaperTrader(
        starting_capital = STARTING_CAPITAL,
        log_file         = 'logs/crypto_trades.json'
    )
    telegram = CryptoTelegram()
    trader.load_state()

    # ==========================================
    # PHASE 1: MARKET CONTEXT
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 1: MARKET CONTEXT")
    print("="*60)

    fear_greed, fg_label = fetcher.get_fear_greed_index()
    btc_dominance        = fetcher.get_bitcoin_dominance()

    print(f"\n   Fear & Greed: {fear_greed} ({fg_label})")
    print(f"   BTC Dominance: {btc_dominance:.1f}%")

    # Market regime based on Fear & Greed
    if fear_greed < 20:
        market_regime = 'EXTREME_FEAR'
        can_trade     = True   # Extreme fear = buy opportunity!
        print("   Regime: EXTREME FEAR - Strong buy opportunity!")
    elif fear_greed < 40:
        market_regime = 'FEAR'
        can_trade     = True
        print("   Regime: FEAR - Cautious buying")
    elif fear_greed < 60:
        market_regime = 'NEUTRAL'
        can_trade     = True
        print("   Regime: NEUTRAL - Normal trading")
    elif fear_greed < 80:
        market_regime = 'GREED'
        can_trade     = True
        print("   Regime: GREED - Be cautious!")
    else:
        market_regime = 'EXTREME_GREED'
        can_trade     = False
        print("   Regime: EXTREME GREED - No new buys!")

    # ==========================================
    # PHASE 2: FETCH CRYPTO DATA
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 2: FETCHING CRYPTO DATA")
    print("="*60)

    crypto_data = fetcher.fetch_all(CRYPTO_PAIRS, days=365)

    if not crypto_data:
        print("   No crypto data fetched!")
        return

    # ==========================================
    # PHASE 3: ML SIGNALS
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 3: ML SIGNALS")
    print("="*60)

    signals        = {}
    current_prices = {}

    for symbol, df in crypto_data.items():
        try:
            # Add features
            df_feat = engine.add_features(
                df,
                fear_greed    = fear_greed,
                btc_dominance = btc_dominance,
            )

            features = engine.get_feature_names()
            available = [f for f in features if f in df_feat.columns]

            if len(df_feat) < 60:
                continue

            # Walk-forward: train on last 180 days
            split       = len(df_feat) - 5
            train_start = max(0, split - 180)
            train       = df_feat.iloc[train_start:split]
            latest      = df_feat.iloc[-1:]

            X_train = train[available]
            y_train = train['target']

            if len(y_train.unique()) < 2:
                continue

            # Always retrain on GitHub (version safety)
            # Cache only used within same session
            model = CryptoEnsemble()
            print(f"   {symbol}: Training models...")
            model.train(X_train, y_train)
            model.save(symbol)

            # Predict
            prediction    = model.predict(latest[available])
            current_price = float(df['close'].iloc[-1])
            current_prices[symbol] = current_price

            # Determine signal
            if prediction >= PREDICTION_THRESHOLD:
                signal = 'BUY'
                emoji  = 'BUY'
            elif prediction <= (1 - PREDICTION_THRESHOLD):
                signal = 'AVOID'
                emoji  = 'AVOID'
            else:
                signal = 'HOLD'
                emoji  = 'HOLD'

            signals[symbol] = {
                'prediction'   : prediction,
                'signal'       : signal,
                'price'        : current_price,
                'fear_greed'   : fear_greed,
                'btc_dominance': btc_dominance,
            }

            print(
                f"   {emoji} {symbol:<12}"
                f" | Score: {prediction:.3f}"
                f" | ${current_price:>10,.2f}"
                f" | {signal}"
            )

        except Exception as e:
            logger.warning(f"Error processing {symbol}: {e}")

    # ==========================================
    # PHASE 4: AI VETO AGENT
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 4: AI VETO AGENT")
    print("="*60)

    if GROQ_API_KEY:
        try:
            from groq import Groq
            groq_client = Groq(api_key=GROQ_API_KEY)
            veto_enabled = True
            print("   Veto Agent: Groq/Llama3 connected ✅")
        except Exception as e:
            veto_enabled = False
            print(f"   Veto Agent: Error - {e}")
    else:
        veto_enabled = False
        print("   Veto Agent: Disabled (no GROQ_API_KEY)")

    def veto_trade(symbol, prediction, price, fear_greed):
        """Ask AI to approve or veto trade."""
        if not veto_enabled:
            return 'APPROVE', 'Veto disabled'

        try:
            prompt = f"""You are a crypto risk manager.
Review this trade signal:

Symbol: {symbol}
Price: ${price:,.2f}
AI Score: {prediction:.3f}
Fear & Greed: {fear_greed} ({'Fear' if fear_greed < 40 else 'Neutral' if fear_greed < 60 else 'Greed'})
Open Positions: {len(trader.positions)}/5

Respond with ONLY JSON:
{{"decision": "APPROVE" or "VETO", "reason": "one sentence"}}

VETO if: extreme greed (>80), score < 0.62, already 5 positions
APPROVE if: score >= 0.62, reasonable market conditions"""

            response = groq_client.chat.completions.create(
                model       = 'llama-3.3-70b-versatile',
                messages    = [{"role": "user", "content": prompt}],
                temperature = 0.1,
                max_tokens  = 100,
            )

            text   = response.choices[0].message.content.strip()
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]

            result   = json.loads(text)
            decision = result.get('decision', 'APPROVE').upper()
            reason   = result.get('reason', '')

            print(f"   Veto [{symbol}]: {decision} - {reason}")
            return decision, reason

        except Exception as e:
            return 'APPROVE', f'Error: {e}'

    # ==========================================
    # PHASE 5: EXECUTE TRADES
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 5: EXECUTING TRADES")
    print("="*60)

    for symbol, data in signals.items():
        if data['signal'] == 'BUY' and can_trade:

            # AI Veto check
            decision, reason = veto_trade(
                symbol     = symbol,
                prediction = data['prediction'],
                price      = data['price'],
                fear_greed = fear_greed,
            )

            if decision == 'VETO':
                print(f"   {symbol}: VETOED - {reason}")
                continue

            # Calculate ATR for stop loss
            atr = None
            try:
                df_atr = crypto_data[symbol]
                tr1    = df_atr['high'] - df_atr['low']
                tr2    = abs(df_atr['high'] - df_atr['close'].shift(1))
                tr3    = abs(df_atr['low'] - df_atr['close'].shift(1))
                true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr    = float(true_range.rolling(14).mean().iloc[-1])
            except Exception:
                pass

            opened = trader.open_position(
                symbol = symbol,
                price  = data['price'],
                signal = data['prediction'],
                reason = market_regime,
                atr    = atr,
            )

            if opened:
                telegram.alert_buy(
                    symbol     = symbol,
                    price      = data['price'],
                    prediction = data['prediction'],
                    fear_greed = fear_greed,
                    reason     = market_regime,
                )

    # ==========================================
    # PHASE 6: POSITION MANAGEMENT
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 6: POSITION MANAGEMENT")
    print("="*60)

    if trader.positions:
        print("\n   Checking stop loss / take profit...")
        for symbol in list(trader.positions.keys()):
            if symbol in current_prices:
                pos   = trader.positions.get(symbol, {})
                entry = pos.get('entry_price', 0)

                trader.update_position(
                    symbol        = symbol,
                    current_price = current_prices[symbol],
                )

                if symbol not in trader.positions:
                    exit_price = current_prices[symbol]
                    pnl        = (exit_price - entry) * pos.get('units', 0)
                    if pnl < 0:
                        telegram.alert_stop_loss(symbol, exit_price, pnl)
                    else:
                        telegram.alert_take_profit(symbol, exit_price, pnl)
    else:
        print("\n   No open positions")

    # ==========================================
    # PHASE 7: PORTFOLIO SUMMARY
    # ==========================================
    print("\n" + "="*60)
    print("PHASE 7: PORTFOLIO SUMMARY")
    print("="*60)

    # Update current prices in positions
    for symbol, pos in trader.positions.items():
        pos['current_price'] = current_prices.get(
            symbol, pos.get('entry_price', 0)
        )

    trader.get_summary(current_prices)
    trader.save_state()

    # Calculate P&L
    total_value = trader.capital + sum(
        pos.get('units', 0) * current_prices.get(
            symbol, pos.get('entry_price', 0)
        )
        for symbol, pos in trader.positions.items()
    )
    total_pnl = total_value - trader.starting_capital
    total_pct = (total_pnl / trader.starting_capital) * 100

    # Send daily summary
    telegram.alert_daily_summary(
        portfolio_value = total_value,
        total_pnl       = total_pnl,
        total_pct       = total_pct,
        positions       = trader.positions,
        fear_greed      = f"{fear_greed} ({fg_label})",
        btc_dominance   = btc_dominance,
    )

    # Save signals for dashboard
    os.makedirs('logs', exist_ok=True)
    with open('logs/crypto_signals.json', 'w') as f:
        json.dump({
            sym: {
                'prediction'   : float(d['prediction']),
                'signal'       : d['signal'],
                'price'        : float(d['price']),
                'fear_greed'   : fear_greed,
                'btc_dominance': btc_dominance,
            }
            for sym, d in signals.items()
        }, f, indent=2)

    print("\n" + "="*60)
    print("CRYPTOEDGE SCAN COMPLETE")
    print("="*60)
    print(f"   Pairs scanned:  {len(signals)}")
    print(f"   Open positions: {len(trader.positions)}")
    print(f"   Portfolio:      ${total_value:,.2f} USDT")
    print(f"   Total PnL:      ${total_pnl:+,.2f} ({total_pct:+.2f}%)")
    print(f"   Fear & Greed:   {fear_greed} ({fg_label})")
    print(f"   BTC Dominance:  {btc_dominance:.1f}%")


def main():
    import pandas as pd
    globals()['pd'] = pd

    try:
        run_crypto_scan()
        print("\nScan complete.")
    except Exception as e:
        logger.error(f"Scan failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()