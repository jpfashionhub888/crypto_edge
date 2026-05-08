# monitoring/crypto_telegram.py
# CRYPTOEDGE - Telegram Alerts

import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')


class CryptoTelegram:

    def __init__(self):
        self.token   = TELEGRAM_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            print("   Telegram not configured")
        else:
            print("   Telegram connected ✅")

    def send_message(self, text):
        if not self.enabled:
            print(f"   [Telegram disabled] {text[:50]}")
            return False

        try:
            url     = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {'chat_id': self.chat_id, 'text': text}
            r       = requests.post(url, json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            logger.warning(f"Telegram error: {e}")
            return False

    def alert_buy(self, symbol, price, prediction, fear_greed, reason):
        text = (
            f"CRYPTOEDGE - BUY SIGNAL\n"
            f"========================\n"
            f"Symbol: {symbol}\n"
            f"Price: ${price:,.2f}\n"
            f"AI Score: {prediction:.3f}\n"
            f"Fear & Greed: {fear_greed}\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self.send_message(text)

    def alert_stop_loss(self, symbol, price, pnl):
        text = (
            f"CRYPTOEDGE - STOP LOSS\n"
            f"=======================\n"
            f"Symbol: {symbol}\n"
            f"Exit: ${price:,.2f}\n"
            f"Loss: ${pnl:.2f}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self.send_message(text)

    def alert_take_profit(self, symbol, price, pnl):
        text = (
            f"CRYPTOEDGE - TAKE PROFIT\n"
            f"=========================\n"
            f"Symbol: {symbol}\n"
            f"Exit: ${price:,.2f}\n"
            f"Profit: +${pnl:.2f}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return self.send_message(text)

    def alert_daily_summary(self, portfolio_value,
                            total_pnl, total_pct,
                            positions, fear_greed,
                            btc_dominance):

        pnl_sign  = '+' if total_pnl >= 0 else ''
        direction = 'UP' if total_pnl >= 0 else 'DOWN'

        pos_text = ''
        if positions:
            for sym, pos in positions.items():
                units   = pos.get('units', 0)
                entry   = pos.get('entry_price', 0)
                current = pos.get('current_price', entry)
                pnl     = (current - entry) * units
                pnl_pct = (current - entry) / entry * 100 if entry > 0 else 0
                p_sign  = '+' if pnl >= 0 else ''
                p_dir   = 'UP' if pnl >= 0 else 'DOWN'
                pos_text += (
                    f"  {sym}\n"
                    f"  Entry: ${entry:,.2f} | Now: ${current:,.2f}\n"
                    f"  PnL: {p_dir} {p_sign}${pnl:.2f} ({p_sign}{pnl_pct:.1f}%)\n\n"
                )
        else:
            pos_text = "  No open positions\n"

        text = (
            f"CRYPTOEDGE DAILY SUMMARY\n"
            f"=========================\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"\n"
            f"Portfolio: ${portfolio_value:,.2f} USDT\n"
            f"Total PnL: {direction} {pnl_sign}${total_pnl:,.2f} ({pnl_sign}{total_pct:.2f}%)\n"
            f"\n"
            f"Market Sentiment:\n"
            f"  Fear & Greed: {fear_greed}\n"
            f"  BTC Dominance: {btc_dominance:.1f}%\n"
            f"\n"
            f"Open Positions:\n"
            f"{pos_text}"
            f"CryptoEdge AI - Automated"
        )

        print("   Sending crypto summary to Telegram...")
        result = self.send_message(text)
        print(f"   Telegram result: {result}")
        return result