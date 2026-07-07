# monitoring/trade_tracker.py
"""
CryptoEdge Trade Tracker

Logs every closed crypto trade to a structured JSON file and
fires Telegram milestone alerts at 25 and 50 closed trades.

File: logs/closed_trades.json
Currency: USDT
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TRADES_FILE  = 'logs/closed_trades.json'
MILESTONE_25 = 25
MILESTONE_50 = 50


class TradeTracker:
    """Records closed crypto trades and computes running statistics."""

    def __init__(self, trades_file: str = TRADES_FILE, telegram=None):
        self.trades_file = trades_file
        self.telegram    = telegram
        self._lock       = threading.Lock()
        self._data       = self._load()

    def record_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        units: float,
        reason: str,
        entry_time: str | None = None,
        exit_time:  str | None = None,
    ) -> dict:
        """Record a single closed crypto trade."""
        now_str  = datetime.now(timezone.utc).isoformat()
        entry_ts = entry_time or now_str
        exit_ts  = exit_time  or now_str

        pnl_usdt = (exit_price - entry_price) * units
        pnl_pct  = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0.0

        try:
            e         = datetime.fromisoformat(entry_ts.replace('Z', '+00:00'))
            x         = datetime.fromisoformat(exit_ts.replace('Z', '+00:00'))
            hold_hours = max(0, (x - e).total_seconds() / 3600)
        except Exception:
            hold_hours = 0

        with self._lock:
            trade_id = len(self._data['trades']) + 1
            trade = {
                'id'          : trade_id,
                'symbol'      : symbol,
                'entry_price' : round(entry_price, 6),
                'exit_price'  : round(exit_price, 6),
                'units'       : round(units, 6),
                'pnl_usdt'    : round(pnl_usdt, 4),
                'pnl_pct'     : round(pnl_pct, 4),
                'reason'      : reason,
                'entry_time'  : entry_ts,
                'exit_time'   : exit_ts,
                'hold_hours'  : round(hold_hours, 1),
            }
            self._data['trades'].append(trade)
            self._data['summary'] = self._compute_summary()
            self._save()
            total = self._data['summary']['total']

        logger.info(
            'Trade #%d: %s %s @ $%.4f -> $%.4f  P&L: $%+.4f (%.1f%%)',
            trade_id, reason, symbol, entry_price, exit_price, pnl_usdt, pnl_pct
        )
        self._check_milestones(total)
        return {'trade': trade, 'summary': self._data['summary']}

    def get_stats(self) -> dict:
        with self._lock:
            return dict(self._data['summary'])

    def get_trades(self) -> list:
        with self._lock:
            return list(self._data['trades'])

    def _compute_summary(self) -> dict:
        trades  = self._data['trades']
        total   = len(trades)
        wins    = [t for t in trades if t['pnl_usdt'] > 0]
        losses  = [t for t in trades if t['pnl_usdt'] <= 0]

        win_count  = len(wins)
        loss_count = len(losses)
        win_rate   = win_count / total if total else 0.0
        total_pnl  = sum(t['pnl_usdt'] for t in trades)
        avg_win    = sum(t['pnl_usdt'] for t in wins)   / win_count  if wins   else 0.0
        avg_loss   = sum(t['pnl_usdt'] for t in losses) / loss_count if losses else 0.0

        gross_profit = sum(t['pnl_usdt'] for t in wins)
        gross_loss   = abs(sum(t['pnl_usdt'] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            float('inf') if gross_profit > 0 else 0.0
        )

        return {
            'total'         : total,
            'wins'          : win_count,
            'losses'        : loss_count,
            'win_rate'      : round(win_rate, 4),
            'total_pnl'     : round(total_pnl, 4),
            'avg_win'       : round(avg_win, 4),
            'avg_loss'      : round(avg_loss, 4),
            'profit_factor' : round(profit_factor, 4) if profit_factor != float('inf') else None,
            'last_updated'  : datetime.now(timezone.utc).isoformat(),
        }

    def _check_milestones(self, total: int) -> None:
        if total not in (MILESTONE_25, MILESTONE_50) or not self.telegram:
            return
        stats = self.get_stats()
        wr    = stats['win_rate'] * 100
        pf    = stats['profit_factor'] or 0
        pnl   = stats['total_pnl']

        if total == MILESTONE_25:
            title = '🎯 25 Crypto Trades Milestone!'
            note  = 'Halfway to live eligibility review.'
        else:
            title = '🚀 50 Crypto Trades Milestone!'
            note  = 'Live eligibility reached! Review go/no-go.'

        msg = (
            f'{title}\n{"=" * 30}\n'
            f'Total trades : {total}\n'
            f'Win rate     : {wr:.1f}%  (need >=55%)\n'
            f'Profit factor: {pf:.2f}  (need >=1.5)\n'
            f'Total P&L    : ${pnl:+,.4f} USDT\n\n'
            f'{note}'
        )
        try:
            self.telegram.send_message(msg)
        except Exception as e:
            logger.warning('Milestone alert failed: %s', e)

    def _load(self) -> dict:
        try:
            with open(self.trades_file) as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                'trades'  : [],
                'summary' : {
                    'total': 0, 'wins': 0, 'losses': 0,
                    'win_rate': 0.0, 'total_pnl': 0.0,
                    'avg_win': 0.0, 'avg_loss': 0.0,
                    'profit_factor': 0.0, 'last_updated': None,
                },
            }
        except Exception as e:
            logger.warning('Could not load trade tracker: %s', e)
            return {'trades': [], 'summary': {}}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.trades_file) or '.', exist_ok=True)
            with open(self.trades_file, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.warning('Could not save trade tracker: %s', e)


def get_trade_stats(trades_file: str = TRADES_FILE) -> dict:
    """Quick read of trade summary."""
    try:
        with open(trades_file) as f:
            data = json.load(f)
        return data.get('summary', {})
    except Exception:
        return {}
