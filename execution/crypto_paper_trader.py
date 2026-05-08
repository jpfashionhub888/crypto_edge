# execution/crypto_paper_trader.py
# CRYPTOEDGE - Paper Trading Engine
# Tracks virtual crypto trades in USDT

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CryptoPaperTrader:
    """
    Paper trading engine for crypto.
    Tracks positions in USDT.
    Starting capital: $10,000 USDT
    """

    def __init__(self,
                 starting_capital = 10000.0,
                 max_position_pct = 0.20,
                 max_positions    = 5,
                 slippage_pct     = 0.001,
                 commission       = 0.001,
                 log_file         = 'logs/crypto_trades.json'):

        self.starting_capital = starting_capital
        self.capital          = starting_capital
        self.max_position_pct = max_position_pct
        self.max_positions    = max_positions
        self.slippage_pct     = slippage_pct
        self.commission       = commission
        self.log_file         = log_file
        self.positions        = {}
        self.trade_history    = []

    def get_position_size(self, price, signal_strength=1.0):
        """Calculate position size in USDT."""
        max_usdt  = self.capital * self.max_position_pct
        adjusted  = max_usdt * min(signal_strength, 1.0)
        units     = adjusted / price
        return max(units, 0)

    def open_position(self, symbol, price, signal, reason='signal', atr=None):
        """Open a new crypto position."""
        if len(self.positions) >= self.max_positions:
            logger.info(f"Max positions reached, skipping {symbol}")
            return False

        if symbol in self.positions:
            logger.info(f"Already in {symbol}")
            return False

        units = self.get_position_size(price, signal)
        if units == 0:
            return False

        # Apply slippage and commission
        fill_price = price * (1 + self.slippage_pct)
        cost       = units * fill_price * (1 + self.commission)

        if cost > self.capital:
            units      = (self.capital * 0.95) / (fill_price * (1 + self.commission))
            cost       = units * fill_price * (1 + self.commission)

        if units == 0:
            return False

        # ATR-based stop loss
        if atr and atr > 0:
            atr_stop = (2 * atr) / price
            stop_loss_pct = max(0.03, min(0.10, atr_stop))
        else:
            stop_loss_pct = 0.05

        self.capital -= cost

        self.positions[symbol] = {
            'units'         : units,
            'entry_price'   : fill_price,
            'entry_date'    : datetime.now().isoformat(),
            'highest_price' : fill_price,
            'signal'        : signal,
            'cost'          : cost,
            'reason'        : reason,
            'stop_loss_pct' : stop_loss_pct,
            'current_price' : fill_price,
        }

        self.trade_history.append({
            'action'   : 'BUY',
            'symbol'   : symbol,
            'units'    : units,
            'price'    : fill_price,
            'cost'     : cost,
            'date'     : datetime.now().isoformat(),
            'reason'   : reason,
        })

        print(f"   BUY {units:.4f} {symbol} @ ${fill_price:.2f} (${cost:.2f})")
        return True

    def close_position(self, symbol, price, reason='signal'):
        """Close a crypto position."""
        if symbol not in self.positions:
            return False

        pos      = self.positions[symbol]
        units    = pos['units']
        entry    = pos['entry_price']

        fill_price = price * (1 - self.slippage_pct)
        revenue    = units * fill_price * (1 - self.commission)
        pnl        = revenue - pos['cost']
        pnl_pct    = (fill_price - entry) / entry

        self.capital += revenue

        self.trade_history.append({
            'action' : 'SELL',
            'symbol' : symbol,
            'units'  : units,
            'price'  : fill_price,
            'revenue': revenue,
            'pnl'    : pnl,
            'pnl_pct': pnl_pct,
            'date'   : datetime.now().isoformat(),
            'reason' : reason,
        })

        direction = "PROFIT" if pnl > 0 else "LOSS"
        print(
            f"   SELL {units:.4f} {symbol} @ ${fill_price:.2f}"
            f" PnL: ${pnl:+.2f} ({pnl_pct:+.1%}) [{direction}]"
        )

        del self.positions[symbol]
        return True

    def update_position(self, symbol, current_price,
                        stop_loss=0.05,
                        take_profit=0.15,
                        trailing_stop=0.04):
        """Check stop loss, take profit, trailing stop."""
        if symbol not in self.positions:
            return

        pos   = self.positions[symbol]
        entry = pos['entry_price']

        # Update prices
        pos['current_price'] = current_price
        if current_price > pos['highest_price']:
            pos['highest_price'] = current_price

        # Use ATR stop if available
        stop_loss = pos.get('stop_loss_pct', stop_loss)
        pnl_pct   = (current_price - entry) / entry

        if pnl_pct <= -stop_loss:
            print(f"   STOP LOSS: {symbol} down {pnl_pct:.1%}")
            self.close_position(symbol, current_price, 'stop_loss')
            return

        if pnl_pct >= take_profit:
            print(f"   TAKE PROFIT: {symbol} up {pnl_pct:.1%}")
            self.close_position(symbol, current_price, 'take_profit')
            return

        drop = (pos['highest_price'] - current_price) / pos['highest_price']
        if drop >= trailing_stop:
            print(f"   TRAILING STOP: {symbol} dropped {drop:.1%} from high")
            self.close_position(symbol, current_price, 'trailing_stop')
            return

    def get_portfolio_value(self, current_prices):
        """Calculate total portfolio value."""
        position_value = sum(
            pos['units'] * current_prices.get(symbol, pos['entry_price'])
            for symbol, pos in self.positions.items()
        )
        return self.capital + position_value

    def get_summary(self, current_prices=None):
        """Print portfolio summary."""
        if current_prices is None:
            current_prices = {}

        position_value = 0.0
        print("\n" + "="*60)
        print("CRYPTOEDGE PAPER TRADING PORTFOLIO")
        print("="*60)
        print(f"   Cash: ${self.capital:,.2f} USDT")

        if self.positions:
            print("\n   Open Positions:")
            for symbol, pos in self.positions.items():
                units   = pos['units']
                entry   = pos['entry_price']
                current = current_prices.get(symbol, entry)
                val     = units * current
                pnl     = val - pos['cost']
                pnl_pct = (current - entry) / entry
                position_value += val
                direction = "UP" if pnl > 0 else "DOWN"
                print(
                    f"      {direction} {symbol}: {units:.4f} units"
                    f" @ ${entry:.2f} now ${current:.2f}"
                    f" PnL: ${pnl:+.2f} ({pnl_pct:+.1%})"
                )

        total     = self.capital + position_value
        total_pnl = total - self.starting_capital
        total_pct = total_pnl / self.starting_capital

        print(f"\n   Position Value: ${position_value:,.2f}")
        print(f"   Total Value:    ${total:,.2f}")
        print(f"   Total PnL:      ${total_pnl:+,.2f} ({total_pct:+.1%})")
        print(f"   Total Trades:   {len(self.trade_history)}")
        print("="*60)
        return total

    def save_state(self):
        """Save state to disk."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        state = {
            'capital'         : self.capital,
            'starting_capital': self.starting_capital,
            'positions'       : self.positions,
            'trade_history'   : self.trade_history,
            'saved_at'        : datetime.now().isoformat(),
        }
        with open(self.log_file, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"   State saved to {self.log_file}")

    def load_state(self):
        """Load state from disk."""
        if not os.path.exists(self.log_file):
            print("   No saved state, starting fresh")
            return

        with open(self.log_file, 'r') as f:
            state = json.load(f)

        self.capital          = state['capital']
        self.starting_capital = state['starting_capital']
        self.positions        = state['positions']
        self.trade_history    = state['trade_history']
        print(f"   State loaded: ${self.capital:,.2f} USDT")
        print(f"   Open positions: {len(self.positions)}")