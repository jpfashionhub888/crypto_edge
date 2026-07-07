# monitoring/model_watchdog.py
"""
CryptoEdge Model Watchdog

Sends a health report via Telegram covering:
  - Portfolio value & P&L (USDT)
  - Trade progress (wins/losses/win rate/profit factor)
  - Model staleness (warns if models older than 3 days — crypto moves fast)
  - Last scan time (warns if no scan in >5h — should scan every 4h)
  - Fear & Greed index (from last scan)
  - Circuit breaker status
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STALE_MODEL_DAYS = 3    # crypto models go stale faster than stock models
STALE_SCAN_HOURS = 5    # warn if no scan in 5h (scans every 4h)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_str(dt: datetime | None = None) -> str:
    if dt is None:
        dt = _utc_now()
    return dt.strftime('%Y-%m-%d %H:%M UTC')


def _check_model_freshness(models_dir: str = 'model_cache') -> tuple[bool, str]:
    try:
        pkl_files = list(Path(models_dir).glob('*.pkl'))
        json_files = list(Path(models_dir).glob('*.json'))
        all_files  = pkl_files + json_files
        if not all_files:
            return True, f'[WARN] No model files in {models_dir}/'
        newest = max(all_files, key=lambda p: p.stat().st_mtime)
        age    = (datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)).days
        ok     = age < STALE_MODEL_DAYS
        return ok, f'{"[OK]" if ok else "[WARN]"} {newest.name} is {age}d old {"" if ok else "(STALE)"}'
    except Exception as e:
        return True, f'[WARN] Could not check model freshness: {e}'


def _check_last_scan(log_file: str = 'logs/crypto_trades.json') -> tuple[bool, str]:
    try:
        with open(log_file) as f:
            data = json.load(f)
        saved_at = data.get('saved_at') or data.get('last_updated')
        if not saved_at:
            return True, '[WARN] No scan timestamp found'
        last  = datetime.fromisoformat(saved_at.replace('Z', '+00:00'))
        age_h = (_utc_now() - last.astimezone(timezone.utc)).total_seconds() / 3600
        ok    = age_h <= STALE_SCAN_HOURS
        return ok, (f'[OK] Last scan: {_utc_str(last.astimezone(timezone.utc))} ({age_h:.1f}h ago)'
                    if ok else
                    f'[WARN] No scan in {age_h:.0f}h (expected every 4h) — check runner')
    except FileNotFoundError:
        return True, '[WARN] Trade log not found — no scans run yet'
    except Exception as e:
        return True, f'[WARN] Could not check last scan: {e}'


def _get_portfolio_snapshot(trade_file: str = 'logs/crypto_trades.json') -> dict:
    try:
        with open(trade_file) as f:
            data = json.load(f)
        return {
            'cash'        : data.get('capital', 0),
            'starting'    : data.get('starting_capital', 10000),
            'pnl'         : data.get('capital', 0) - data.get('starting_capital', 10000),
            'n_positions' : len(data.get('positions', {})),
        }
    except Exception:
        return {}


def _get_trade_stats(trades_file: str = 'logs/closed_trades.json') -> dict:
    try:
        with open(trades_file) as f:
            data = json.load(f)
        return data.get('summary', {})
    except Exception:
        return {}


def _get_fear_greed() -> str:
    try:
        with open('logs/crypto_signals.json') as f:
            signals = json.load(f)
        fg = signals.get('fear_greed', '?')
        label = signals.get('fg_label', '')
        return f'{fg} ({label})'
    except Exception:
        return 'N/A'


def _get_cb_status(cb_file: str = 'logs/circuit_breaker.json') -> str:
    try:
        with open(cb_file) as f:
            cb = json.load(f)
        if cb.get('triggered'):
            return f"[TRIGGERED] {cb.get('trigger_reason','Unknown')}"
        return '[OK] Clear'
    except Exception:
        return '[?] Unknown'


def run_watchdog_report(telegram=None) -> str:
    """Build and optionally send the health report."""

    pf      = _get_portfolio_snapshot()
    cash    = pf.get('cash', 0)
    start   = pf.get('starting', 10000)
    pnl     = pf.get('pnl', 0)
    n_pos   = pf.get('n_positions', 0)
    pnl_pct = (pnl / start * 100) if start else 0

    ts      = _get_trade_stats()
    total   = ts.get('total', 0)
    wr      = ts.get('win_rate', 0) * 100
    pf_val  = ts.get('profit_factor') or 0
    tpnl    = ts.get('total_pnl', 0)
    goal    = 50

    wr_flag = '[OK]' if wr >= 55 else ('[WARN]' if total >= 10 else '[?]')
    pf_flag = '[OK]' if pf_val >= 1.5 else ('[WARN]' if total >= 10 else '[?]')
    bar     = '#' * min(total, 25) + '.' * (25 - min(total, 25)) + f' {total}/{goal}'

    model_stale, model_msg = _check_model_freshness()
    scan_stale,  scan_msg  = _check_last_scan()
    cb_status               = _get_cb_status()
    fear_greed              = _get_fear_greed()

    alerts = []
    if model_stale:
        alerts.append('[WARN] Models stale — retrain needed')
    if scan_stale:
        alerts.append('[WARN] Scan overdue — check GitHub Actions')
    if 'TRIGGERED' in cb_status:
        alerts.append('[!!] Circuit breaker triggered')

    alert_block = '\n  '.join(alerts) if alerts else '[OK] All systems normal'
    sign_pnl    = '+' if pnl  >= 0 else ''
    sign_tpnl   = '+' if tpnl >= 0 else ''

    report = (
        f'[CryptoEdge] Watchdog Report\n'
        f'{"=" * 32}\n'
        f'{_utc_str()}\n\n'
        f'Portfolio (USDT)\n'
        f'  Cash:      ${cash:,.2f}\n'
        f'  P&L:       {sign_pnl}${pnl:,.2f} ({sign_pnl}{pnl_pct:.1f}%)\n'
        f'  Positions: {n_pos}\n\n'
        f'Trade Progress ({total}/{goal})\n'
        f'  [{bar}]\n'
        f'  Win rate:   {wr_flag} {wr:.1f}%\n'
        f'  Profit fac: {pf_flag} {pf_val:.2f}\n'
        f'  Closed P&L: {sign_tpnl}${tpnl:,.4f} USDT\n\n'
        f'Market\n'
        f'  Fear & Greed: {fear_greed}\n\n'
        f'Health\n'
        f'  {model_msg}\n'
        f'  {scan_msg}\n'
        f'  CB: {cb_status}\n\n'
        f'Alerts\n'
        f'  {alert_block}'
    )

    if total >= goal:
        report += '\n\n[!!] 50-trade milestone! Review live eligibility.'

    if telegram:
        try:
            telegram.send_message(report)
            logger.info('Watchdog report sent')
        except Exception as e:
            logger.warning('Watchdog send failed: %s', e)

    return report


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    telegram = None
    try:
        from monitoring.crypto_telegram import CryptoTelegram
        telegram = CryptoTelegram()
    except Exception:
        pass
    print(run_watchdog_report(telegram=telegram))
