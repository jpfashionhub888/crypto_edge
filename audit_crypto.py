# -*- coding: utf-8 -*-
# audit_crypto.py
"""
CryptoEdge Deep Audit — 10 system health checks.

Usage:
  python audit_crypto.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

PASS = '  [OK]  '
FAIL = '  [FAIL]'
WARN = '  [WARN]'

results = []

def check(name: str, ok: bool, detail: str = '') -> bool:
    flag = PASS if ok else FAIL
    line = f'{flag} {name}'
    if detail:
        line += f'  --  {detail}'
    print(line)
    results.append({'name': name, 'ok': ok, 'detail': detail})
    return ok


def check_env_vars():
    print('\n-- Environment Variables ----------------------------------------')
    required = ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'GROQ_API_KEY']
    optional = ['COINBASE_API_KEY', 'COINBASE_SECRET', 'GITHUB_TOKEN']
    all_ok = True
    for var in required:
        val = os.getenv(var, '')
        ok  = bool(val) and 'YOUR_' not in val
        check(f'${var}', ok, '(set)' if ok else 'MISSING')
        all_ok = all_ok and ok
    for var in optional:
        val = os.getenv(var, '')
        flag = PASS if val else WARN
        print(f'{flag} ${var}  --  {"set" if val else "not set (optional)"}')
    return all_ok


def check_telegram():
    print('\n-- Telegram Connection ------------------------------------------')
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return check('Telegram getMe', False, 'No token')
    if not _HAS_REQUESTS:
        return check('Telegram getMe', False, 'requests not installed')
    try:
        resp = requests.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10)
        data = resp.json()
        if data.get('ok'):
            bot = data['result']
            return check('Telegram getMe', True, f"@{bot.get('username')} ({bot.get('first_name')})")
        return check('Telegram getMe', False, str(data.get('description', 'Error')))
    except Exception as e:
        return check('Telegram getMe', False, str(e))


def check_circuit_breaker():
    print('\n-- Circuit Breaker ----------------------------------------------')
    cb_file = 'logs/circuit_breaker.json'
    if not os.path.exists(cb_file):
        print(f'{WARN} circuit_breaker.json  --  not found (created on first scan)')
        return True
    try:
        with open(cb_file) as f:
            cb = json.load(f)
        triggered = cb.get('triggered', False)
        return check('Circuit breaker', not triggered,
                     'Clear' if not triggered else f"TRIGGERED: {cb.get('trigger_reason','')}")
    except Exception as e:
        return check('Circuit breaker', False, str(e))


def check_trade_tracker():
    print('\n-- Trade Tracker ------------------------------------------------')
    try:
        sys.path.insert(0, os.getcwd())
        from monitoring.trade_tracker import get_trade_stats
        check('monitoring.trade_tracker import', True)
    except ImportError as e:
        check('monitoring.trade_tracker import', False, str(e))
        return False

    trades_file = 'logs/closed_trades.json'
    if not os.path.exists(trades_file):
        print(f'{WARN} {trades_file}  --  not found (created on first closed trade)')
        return True
    try:
        stats = get_trade_stats(trades_file)
        total = stats.get('total', 0)
        wr    = stats.get('win_rate', 0) * 100
        pnl   = stats.get('total_pnl', 0)
        pf    = stats.get('profit_factor') or 0
        return check('Trade file readable', True,
                     f'{total} trades, wr={wr:.1f}%, P&L=${pnl:+,.4f}, PF={pf:.2f}')
    except Exception as e:
        return check('Trade file readable', False, str(e))


def check_model_freshness():
    print('\n-- Model Freshness ----------------------------------------------')
    models_dir = 'model_cache'
    all_files  = (list(Path(models_dir).glob('*.pkl')) +
                  list(Path(models_dir).glob('*.json'))) if Path(models_dir).exists() else []
    if not all_files:
        print(f'{WARN} Models  --  no files in {models_dir}/ (will populate on first scan)')
        return True
    newest = max(all_files, key=lambda p: p.stat().st_mtime)
    age    = (datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)).days
    ok     = age < 3   # crypto models stale faster
    return check('Model freshness (3d limit)', ok,
                 f'{newest.name} is {age}d old {"" if ok else "(STALE)"}')


def check_env_not_committed():
    print('\n-- Git Security -------------------------------------------------')
    try:
        result = subprocess.run(['git', 'ls-files', '.env'],
                                capture_output=True, text=True, cwd='.')
        committed = bool(result.stdout.strip())
        return check('.env not in git', not committed,
                     'DANGER: committed!' if committed else 'Safe')
    except Exception as e:
        print(f'{WARN} Could not check git: {e}')
        return True


def check_bot_control():
    print('\n-- Bot Control State --------------------------------------------')
    ctrl_file = 'logs/bot_control.json'
    if not os.path.exists(ctrl_file):
        print(f'{WARN} bot_control.json  --  not found (created on first /pause command)')
        return True
    try:
        with open(ctrl_file) as f:
            ctrl = json.load(f)
        paused = ctrl.get('paused', False)
        return check('Bot control', not paused,
                     'Running' if not paused else f"PAUSED: {ctrl.get('reason','')}")
    except Exception as e:
        return check('Bot control', False, str(e))


def check_logs_dir():
    print('\n-- Filesystem ---------------------------------------------------')
    os.makedirs('logs', exist_ok=True)
    test = 'logs/.audit_write_test'
    try:
        open(test, 'w').close()
        os.remove(test)
        return check('logs/ writable', True)
    except Exception as e:
        return check('logs/ writable', False, str(e))


def check_imports():
    print('\n-- Module Imports -----------------------------------------------')
    modules = [
        ('monitoring.command_listener', 'start_command_listener'),
        ('monitoring.trade_tracker',    'TradeTracker'),
        ('monitoring.model_watchdog',   'run_watchdog_report'),
        ('monitoring.crypto_telegram',  'CryptoTelegram'),
        ('execution.crypto_paper_trader', 'CryptoPaperTrader'),
        ('risk_circuit_breaker',        'RiskCircuitBreaker'),
    ]
    all_ok = True
    for module, attr in modules:
        try:
            mod = __import__(module, fromlist=[attr])
            getattr(mod, attr)
            check(f'{module}.{attr}', True)
        except Exception as e:
            check(f'{module}.{attr}', False, str(e))
            all_ok = False
    return all_ok


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    print('\n' + '=' * 55)
    print('  CRYPTOEDGE DEEP AUDIT')
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print('=' * 55)

    check_env_vars()
    check_telegram()
    check_circuit_breaker()
    check_trade_tracker()
    check_model_freshness()
    check_env_not_committed()
    check_bot_control()
    check_logs_dir()
    check_imports()

    total   = len(results)
    passed  = sum(1 for r in results if r['ok'])
    failed  = total - passed
    failures = [r for r in results if not r['ok']]

    print('\n' + '=' * 55)
    print(f'  AUDIT RESULT: {passed}/{total} checks passed')
    if failures:
        print(f'  FAILURES ({failed}):')
        for r in failures:
            print(f'    [FAIL] {r["name"]}  --  {r["detail"]}')
    else:
        print('  [OK] All checks passed -- CryptoEdge is healthy!')
    print('=' * 55 + '\n')
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
