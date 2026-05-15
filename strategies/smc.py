import numpy as np
import pandas as pd


def detect_order_blocks(df: pd.DataFrame, lookback: int = 100, min_impulse_pct: float = 1.0, min_candles: int = 3):
    """
    Bullish OB: candle bearish terakhir sebelum impulse naik kuat
    Bearish OB: candle bullish terakhir sebelum impulse turun kuat
    """
    highs  = df['high'].values
    lows   = df['low'].values
    opens  = df['open'].values
    closes = df['close'].values
    n      = len(df)
    start  = max(0, n - lookback)

    bull_obs, bear_obs = [], []

    for i in range(start, n - min_candles):
        future_high = max(highs[i+1 : i+1+min_candles])
        future_low  = min(lows[i+1  : i+1+min_candles])
        up_move   = (future_high - closes[i]) / closes[i] * 100
        down_move = (closes[i] - future_low)  / closes[i] * 100

        ob_high = float(highs[i])
        ob_low  = float(lows[i])
        ob_range = ob_high - ob_low
        if ob_range == 0:
            continue

        mid    = round((ob_high + ob_low) / 2, 6)
        # OTE zone: Fibonacci 0.62–0.79 dari bawah OB (zona entry presisi Kevin Sailly)
        ote_lo = round(ob_low  + ob_range * 0.21, 6)   # 79% dari atas
        ote_hi = round(ob_low  + ob_range * 0.38, 6)   # 62% dari atas

        # Bullish OB
        if closes[i] < opens[i] and up_move >= min_impulse_pct:
            bull_obs.append({
                'type': 'bullish', 'index': i,
                'ob_high': round(ob_high, 6), 'ob_low': round(ob_low, 6),
                'midpoint': mid, 'ote_high': ote_hi, 'ote_low': ote_lo,
                'impulse_pct': round(up_move, 2),
            })

        # Bearish OB — OTE di bagian atas OB
        if closes[i] > opens[i] and down_move >= min_impulse_pct:
            ote_hi_b = round(ob_low + ob_range * 0.79, 6)
            ote_lo_b = round(ob_low + ob_range * 0.62, 6)
            bear_obs.append({
                'type': 'bearish', 'index': i,
                'ob_high': round(ob_high, 6), 'ob_low': round(ob_low, 6),
                'midpoint': mid, 'ote_high': ote_hi_b, 'ote_low': ote_lo_b,
                'impulse_pct': round(down_move, 2),
            })

    bull_obs = sorted(bull_obs, key=lambda x: x['index'], reverse=True)[:5]
    bear_obs = sorted(bear_obs, key=lambda x: x['index'], reverse=True)[:5]
    return bull_obs, bear_obs


def detect_fvg(df: pd.DataFrame, lookback: int = 60, min_gap_pct: float = 0.05):
    """
    Fair Value Gap (imbalance):
    Bullish FVG: lows[i] > highs[i-2]
    Bearish FVG: highs[i] < lows[i-2]
    """
    highs  = df['high'].values
    lows   = df['low'].values
    n      = len(df)
    start  = max(2, n - lookback)

    bull_fvgs, bear_fvgs = [], []

    for i in range(start, n):
        # Bullish FVG
        if lows[i] > highs[i-2]:
            gap_pct = (lows[i] - highs[i-2]) / highs[i-2] * 100
            if gap_pct >= min_gap_pct:
                bull_fvgs.append({
                    'type': 'bullish', 'index': i,
                    'fvg_high': round(float(lows[i]), 6),
                    'fvg_low':  round(float(highs[i-2]), 6),
                    'midpoint': round((float(lows[i]) + float(highs[i-2])) / 2, 6),
                    'gap_pct': round(gap_pct, 3),
                })

        # Bearish FVG
        if highs[i] < lows[i-2]:
            gap_pct = (lows[i-2] - highs[i]) / lows[i-2] * 100
            if gap_pct >= min_gap_pct:
                bear_fvgs.append({
                    'type': 'bearish', 'index': i,
                    'fvg_high': round(float(lows[i-2]), 6),
                    'fvg_low':  round(float(highs[i]), 6),
                    'midpoint': round((float(lows[i-2]) + float(highs[i])) / 2, 6),
                    'gap_pct': round(gap_pct, 3),
                })

    cur_high = float(df['high'].iloc[-1])
    cur_low  = float(df['low'].iloc[-1])

    # Tandai yang sudah filled
    for f in bull_fvgs:
        f['filled'] = cur_low <= f['fvg_high']
    for f in bear_fvgs:
        f['filled'] = cur_high >= f['fvg_low']

    bull_fvgs = [f for f in sorted(bull_fvgs, key=lambda x: x['index'], reverse=True) if not f['filled']][:3]
    bear_fvgs = [f for f in sorted(bear_fvgs, key=lambda x: x['index'], reverse=True) if not f['filled']][:3]
    return bull_fvgs, bear_fvgs


def detect_liquidity_levels(df: pd.DataFrame, lookback: int = 100, tolerance_pct: float = 0.15):
    """
    Equal highs = buy-side liquidity (target untuk MM sweep ke atas)
    Equal lows  = sell-side liquidity (target untuk MM sweep ke bawah)
    """
    highs = df['high'].values[-lookback:]
    lows  = df['low'].values[-lookback:]

    swing_highs, swing_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append(float(highs[i]))
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append(float(lows[i]))

    def group_levels(levels):
        if not levels:
            return []
        levels = sorted(levels)
        groups, cur = [], [levels[0]]
        for lv in levels[1:]:
            if (lv - cur[0]) / cur[0] * 100 <= tolerance_pct:
                cur.append(lv)
            else:
                if len(cur) >= 2:
                    groups.append({'level': round(np.mean(cur), 6), 'touches': len(cur)})
                cur = [lv]
        if len(cur) >= 2:
            groups.append({'level': round(np.mean(cur), 6), 'touches': len(cur)})
        return sorted(groups, key=lambda x: x['touches'], reverse=True)[:5]

    eq_highs = group_levels(swing_highs)
    eq_lows  = group_levels(swing_lows)

    for h in eq_highs:
        h['type'] = 'equal_high'
        h['label'] = 'Buy-side Liquidity'
    for l in eq_lows:
        l['type'] = 'equal_low'
        l['label'] = 'Sell-side Liquidity'

    return eq_highs, eq_lows


def analisa_smc(df: pd.DataFrame, symbol: str = '') -> dict:
    """
    Full SMC analysis — Order Block + OTE + FVG + Liquidity
    """
    price = float(df['close'].iloc[-1])

    bull_obs, bear_obs   = detect_order_blocks(df)
    bull_fvgs, bear_fvgs = detect_fvg(df)
    eq_highs, eq_lows    = detect_liquidity_levels(df)

    # Nearest OB dari harga sekarang
    def nearest_ob(obs, above: bool):
        candidates = [o for o in obs if (o['ob_high'] >= price * 0.95 if above else o['ob_low'] <= price * 1.05)]
        if not candidates:
            return None
        return min(candidates, key=lambda o: abs(o['ob_high'] - price) if above else abs(o['ob_low'] - price))

    near_bull = nearest_ob(bull_obs, above=False)
    near_bear = nearest_ob(bear_obs, above=True)

    in_bull_ob  = near_bull and near_bull['ob_low']  <= price <= near_bull['ob_high']
    in_bull_ote = near_bull and near_bull['ote_low'] <= price <= near_bull['ote_high']
    in_bear_ob  = near_bear and near_bear['ob_low']  <= price <= near_bear['ob_high']
    in_bear_ote = near_bear and near_bear['ote_low'] <= price <= near_bear['ote_high']

    # Liquidity terdekat
    liq_above = min((h for h in eq_highs if h['level'] > price), key=lambda x: x['level'], default=None)
    liq_below = max((l for l in eq_lows  if l['level'] < price), key=lambda x: x['level'], default=None)

    # Bias SMC
    if in_bull_ote:
        bias = 'BULLISH'
        entry_quality = 'OPTIMAL'
    elif in_bull_ob:
        bias = 'BULLISH'
        entry_quality = 'VALID'
    elif in_bear_ote:
        bias = 'BEARISH'
        entry_quality = 'OPTIMAL'
    elif in_bear_ob:
        bias = 'BEARISH'
        entry_quality = 'VALID'
    else:
        bias = 'NETRAL'
        entry_quality = 'WAIT'

    return {
        'symbol': symbol,
        'price': price,
        'bias': bias,
        'entry_quality': entry_quality,
        'in_bull_ob': bool(in_bull_ob),
        'in_bull_ote': bool(in_bull_ote),
        'in_bear_ob': bool(in_bear_ob),
        'in_bear_ote': bool(in_bear_ote),
        'nearest_bull_ob': near_bull,
        'nearest_bear_ob': near_bear,
        'bullish_obs': bull_obs[:3],
        'bearish_obs': bear_obs[:3],
        'bullish_fvgs': bull_fvgs,
        'bearish_fvgs': bear_fvgs,
        'liquidity_above': liq_above,
        'liquidity_below': liq_below,
        'equal_highs': eq_highs,
        'equal_lows': eq_lows,
    }
