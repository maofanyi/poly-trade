"""Batch run TradingAgents on portfolio + watchlist stocks"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.chdir(r'G:\trade\TradingAgents')

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config['llm_provider'] = 'deepseek'
config['deep_think_llm'] = 'deepseek-chat'
config['quick_think_llm'] = 'deepseek-chat'
config['output_language'] = 'Chinese'
config['max_debate_rounds'] = 1
config['temperature'] = 0.2

results = {}
ta = TradingAgentsGraph(debug=False, config=config)

tickers = ["SOXL", "NVDA", "TSLA", "MU", "SNDK", "TSM"]
for i, ticker in enumerate(tickers):
    print(f'\n{"="*60}')
    print(f'[{i+1}/6] Analyzing {ticker}...')
    print(f'{"="*60}')
    try:
        _, decision = ta.propagate(ticker, "2026-06-01")
        results[ticker] = decision
        print(f'>>> {ticker} DONE')
    except Exception as e:
        results[ticker] = f"ERROR: {str(e)}"
        print(f'>>> {ticker} FAILED: {e}')

out_path = r'G:\trade\ta_results.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nResults saved to {out_path}')
