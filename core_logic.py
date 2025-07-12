# core_logic.py
import streamlit as st
import requests
import pandas as pd
import pandas_ta as ta
import os
import csv
from datetime import datetime, timedelta
from config import API_KEY

# --- Shared & Cached API Calls ---
@st.cache_data(ttl=900)
def get_api_data(url, params):
    """A generic, cached function to fetch data from CoinGecko."""
    headers = {'accept': 'application/json', 'x-cg-demo-api-key': API_KEY}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=900)
def get_top_coins_data():
    """
    Specifically fetches the top 25 coins market data.
    CORRECTED LOGIC: It now updates the session state timestamp when it runs.
    """
    # This line will ONLY execute on a cache miss (i.e., when the API is actually called)
    st.session_state.last_api_call = datetime.now()
    return get_api_data("https://api.coingecko.com/api/v3/coins/markets", {'vs_currency': 'usd', 'order': 'market_cap_desc', 'per_page': 25, 'page': 1})

# --- Database / CSV Management ---
TRADE_FILE = 'paper_trades.csv'
TRADE_AMOUNT_USD = 10.00

def setup_database():
    """Creates the CSV for trades if it doesn't exist, now with a 'trade_type' column."""
    if not os.path.exists(TRADE_FILE):
        with open(TRADE_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'coin_id', 'name', 'symbol', 'buy_price', 'quantity', 'trade_type'])

def log_trade(coin, analysis, trade_type):
    """
    Logs a new dummy trade. Now accepts a trade_type ('auto' or 'manual').
    Prevents duplicate 'auto' trades within 24 hours.
    """
    if trade_type == 'auto':
        if os.path.exists(TRADE_FILE):
            try:
                trades_df = pd.read_csv(TRADE_FILE)
                if not trades_df.empty:
                    trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp'])
                    recent_trades = trades_df[
                        (trades_df['coin_id'] == coin['id']) &
                        (trades_df['trade_type'] == 'auto') &
                        (trades_df['timestamp'] > datetime.now() - timedelta(days=1))
                    ]
                    if not recent_trades.empty:
                        return
            except pd.errors.EmptyDataError:
                pass

    with open(TRADE_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            coin['id'],
            coin['name'],
            coin['symbol'].upper(),
            analysis['current_price'],
            TRADE_AMOUNT_USD / analysis['current_price'],
            trade_type
        ])
    st.toast(f"Logged a ${TRADE_AMOUNT_USD} {trade_type} trade for {coin['name']}!", icon="✅")


# --- Analysis Function ---
def calculate_indicators_and_score(coin_data, hist_df):
    hist_df.ta.rsi(close=hist_df['price'], append=True)
    hist_df.ta.macd(close=hist_df['price'], append=True)
    hist_df.ta.bbands(close=hist_df['price'], length=20, append=True)
    hist_df.ta.sma(close=hist_df['price'], length=50, append=True)

    latest = hist_df.iloc[-1]
    latest_rsi = latest['RSI_14']
    latest_macd = latest['MACD_12_26_9']
    latest_macd_signal = latest['MACDs_12_26_9']
    lower_bollinger_band = latest['BBL_20_2.0']
    sma_50 = latest['SMA_50']

    current_price = coin_data['current_price']
    ath = coin_data['ath']
    atl = coin_data['atl']
    upside_potential = ((ath - current_price) / current_price) * 100
    downside_potential = ((current_price - atl) / current_price) * 100

    score = 0
    weights = {'potential': 0.30, 'rsi': 0.25, 'macd': 0.20, 'bollinger': 0.15, 'trend': 0.10}
    
    potential_score = min(upside_potential / (downside_potential + 1) * 25, 100)
    rsi_score = 100 - latest_rsi
    macd_score = min(100, max(0, 50 + (latest_macd - latest_macd_signal) * 15))
    bollinger_score = 100 if current_price < lower_bollinger_band else 60 if current_price < hist_df['BBM_20_2.0'].iloc[-1] else 0
    trend_score = 100 if current_price > sma_50 else 0
    
    score = (potential_score * weights['potential'] + rsi_score * weights['rsi'] + macd_score * weights['macd'] + 
             bollinger_score * weights['bollinger'] + trend_score * weights['trend'])

    return {"score": int(score), "current_price": current_price, "rsi": int(latest_rsi)}