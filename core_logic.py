# core_logic.py
import requests
import pandas as pd
import pandas_ta as ta

# This function is now enhanced with more indicators
def calculate_indicators_and_score(coin_data, hist_df):
    """
    Performs advanced analysis on coin data.
    NEW: Includes Bollinger Bands and 50-Day Moving Average for trend confirmation.
    """
    # --- Indicator Calculation ---
    # Explicitly tell pandas_ta to use the 'price' column.
    hist_df.ta.rsi(close=hist_df['price'], append=True)
    hist_df.ta.macd(close=hist_df['price'], append=True)
    # New: Bollinger Bands (provides volatility bands)
    hist_df.ta.bbands(close=hist_df['price'], length=20, append=True)
    # New: 50-Day Simple Moving Average (to determine long-term trend)
    hist_df.ta.sma(close=hist_df['price'], length=50, append=True)

    # --- Get Latest Values ---
    latest = hist_df.iloc[-1] # Get the most recent row of data
    latest_rsi = latest['RSI_14']
    latest_macd = latest['MACD_12_26_9']
    latest_macd_signal = latest['MACDs_12_26_9']
    lower_bollinger_band = latest['BBL_20_2.0']
    sma_50 = latest['SMA_50']

    # --- Potential Calculation ---
    current_price = coin_data['current_price']
    ath = coin_data['ath']
    atl = coin_data['atl']
    upside_potential = ((ath - current_price) / current_price) * 100
    downside_potential = ((current_price - atl) / current_price) * 100

    # --- ADVANCED SPOT SCORE CALCULATION (0-100) ---
    score = 0
    # New weights for the advanced model
    weights = {'potential': 0.30, 'rsi': 0.25, 'macd': 0.20, 'bollinger': 0.15, 'trend': 0.10}
    breakdown = {}

    # 1. Potential Score
    potential_ratio = upside_potential / (downside_potential + 1)
    potential_score = min(potential_ratio * 25, 100)
    score += potential_score * weights['potential']
    breakdown['Potential Score'] = potential_score * weights['potential']

    # 2. RSI Score (lower is better)
    rsi_score = 100 - latest_rsi
    score += rsi_score * weights['rsi']
    breakdown['RSI Score'] = rsi_score * weights['rsi']

    # 3. MACD Score (bullish cross is better)
    macd_score = min(100, max(0, 50 + (latest_macd - latest_macd_signal) * 15))
    score += macd_score * weights['macd']
    breakdown['MACD Score'] = macd_score * weights['macd']
    
    # 4. Bollinger Band Score (price near/below lower band is a strong buy signal)
    bollinger_score = 0
    if current_price < lower_bollinger_band:
        bollinger_score = 100  # Strong signal
    elif current_price < hist_df['BBM_20_2.0'].iloc[-1]: # Price below middle band
        bollinger_score = 60
    score += bollinger_score * weights['bollinger']
    breakdown['Bollinger Score'] = bollinger_score * weights['bollinger']

    # 5. Trend Score (price above long-term average is bullish)
    trend_score = 100 if current_price > sma_50 else 0
    score += trend_score * weights['trend']
    breakdown['Trend Score'] = trend_score * weights['trend']

    return {
        "score": int(score), "rsi": int(latest_rsi), "upside": int(upside_potential),
        "downside": int(downside_potential), "macd": latest_macd, "macd_signal": latest_macd_signal,
        "current_price": current_price, "sma_50": sma_50, "lower_bb": lower_bollinger_band,
        "score_breakdown": breakdown
    }