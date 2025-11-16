from backend.evaluation.backtesting import BacktestEngine
import pandas as pd

preds = pd.DataFrame([
    {"game_date": "2025-01-01", "player": "A", "predicted_value": 10, "over_probability": 0.7, "confidence": 0.9, "decimal_odds": 2.5},
    {"game_date": "2025-01-02", "player": "B", "predicted_value": 8, "over_probability": 0.6, "confidence": 0.8, "decimal_odds": 1.8},
    {"game_date": "2025-01-03", "player": "C", "predicted_value": 7, "over_probability": 0.4, "confidence": 0.95, "decimal_odds": 2.0},
])

actuals = pd.DataFrame([
    {"game_date": "2025-01-01", "player": "A", "actual_value": 11},
    {"game_date": "2025-01-02", "player": "B", "actual_value": 9},
    {"game_date": "2025-01-03", "player": "C", "actual_value": 6},
])

engine = BacktestEngine(preds)
merged = engine._merge_with_actuals(engine.load_actuals(actuals))
print("Merged:\n", merged)

# run with debug prints by reusing logic from run()
initial_bankroll=1000
bankroll = float(initial_bankroll)
rows=[]
for _, r in merged.iterrows():
    print('\nRow:', r.to_dict())
    if pd.isna(r.get('actual_value')):
        print('  -> skip unresolved')
        continue
    raw_ev = r.get('expected_value', None)
    ev = float(raw_ev or 0.0)
    conf = float(r.get('confidence', 0.0) or 0.0)
    p = float(r.get('over_probability', 0.0) or 0.0)
    line = r.get('line')
    print(f'  raw_ev={raw_ev} ev={ev} conf={conf} p={p}')
    odds = float(r.get('decimal_odds', 2.0) or 2.0)
    b = odds - 1.0
    if raw_ev is None or (isinstance(raw_ev, (int,float)) and float(raw_ev)==0.0):
        ev = b * p - (1.0 - p)
        print('  computed ev from odds:', ev)
    if ev <= 0:
        print('  -> skip EV<=0')
        continue
    if conf < 0.5:
        print('  -> skip conf < min')
        continue
    if b > 0:
        numerator = b * p - (1.0 - p)
        kelly_f = max(0.0, numerator / b) if numerator > 0 else 0.0
    else:
        kelly_f = max(0.0, 2.0 * p - 1.0)
    print('  odds, b, numerator, kelly_f:', odds, b, numerator if b>0 else None, kelly_f)
    stake_fraction = min(kelly_f, 0.02)
    stake = bankroll * stake_fraction
    print('  stake_fraction, stake:', stake_fraction, stake)
    if stake <= 0:
        print('  -> stake <=0 continue')
        continue
    actual = float(r.get('actual_value'))
    if pd.isna(line):
        line_check = float(r.get('predicted_value', 0.0) or 0.0)
        won = actual > line_check
    else:
        won = actual > float(line)
    profit = stake * (odds - 1.0) if won else -stake
    bankroll += profit
    rows.append({'player': r['player'], 'odds':odds, 'p':p, 'ev':ev, 'kelly_f':kelly_f, 'stake':stake, 'won':won, 'profit':profit, 'bankroll':bankroll})

print('\nSimulated bets:')
for row in rows:
    print(row)

print('\nTotal bets:', len(rows))


print('\nRunning engine.run for result:')
res = engine.run(actuals, initial_bankroll=initial_bankroll, min_confidence=0.5)
print('result with require_ev_positive=True ->', res)
res2 = engine.run(actuals, initial_bankroll=initial_bankroll, min_confidence=0.5, require_ev_positive=False)
print('result with require_ev_positive=False ->', res2)
