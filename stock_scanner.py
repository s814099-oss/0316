import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# SSL 繞過
ssl._create_default_https_context = ssl._create_unverified_context

# --- 核心修改：增加異常處理與更長延遲 ---
def fetch_batch_data(batch):
    """帶有重試機制的下載函式"""
    for attempt in range(3): # 最多重試 3 次
        try:
            # 必須使用 threads=False，減少並發請求
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=False)
            return data
        except Exception as e:
            if "Too Many Requests" in str(e):
                time.sleep(60 * (attempt + 1)) # 第一次失敗睡 60 秒，第二次 120 秒...
            else:
                time.sleep(10)
    return None

def run_scanner(tickers, min_vol):
    res_20pct, res_high = [], []
    batch_size = 5 # 關鍵：將批次縮小到 5，大幅降低 Yahoo 壓力
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress_bar = st.progress(0)
    
    for i, batch in enumerate(batches):
        progress_bar.progress((i + 1) / len(batches))
        
        data = fetch_batch_data(batch)
        if data is None or data.empty:
            continue
            
        for s in batch:
            if s not in data: continue
            df = data[s].dropna()
            # 嚴格檢查數據長度與成交量
            if len(df) < 120 or float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
            
            # 計算指標
            vol_ratio = df['Volume'].rolling(5).mean().iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            if vol_ratio > 1.85 and k_val > 80:
                cur_close = float(df['Close'].iloc[-1])
                # 策略條件
                if (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4] >= 0.20:
                    res_20pct.append({"代號": s.replace(".TW", ""), "現價": cur_close})
                if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                    res_high.append({"代號": s.replace(".TW", ""), "現價": cur_close})
        
        # 關鍵：每跑完一批就隨機冷卻
        time.sleep(random.uniform(5.0, 10.0))
            
    return pd.DataFrame(res_20pct), pd.DataFrame(res_high)
