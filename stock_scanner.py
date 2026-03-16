import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
from ta.momentum import StochasticOscillator

# SSL 繞過
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股精準掃描器", layout="wide")

# 1. 核心邏輯：只下載交易量大的股票，避開 Yahoo 封鎖
def run_scanner(tickers, min_vol):
    res_20pct = []
    res_high = []
    
    # 限制每次處理的數量，避免記憶體溢出
    batch_size = 5
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress = st.progress(0)
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        try:
            # 必須使用 threads=False，減少被封鎖風險
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=False)
            
            for s in batch:
                if s not in data: continue
                df = data[s].dropna()
                if len(df) < 120 or float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
                
                # 計算指標
                vol_ratio = df['Volume'].rolling(5).mean().iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 篩選
                if vol_ratio > 1.85 and k_val > 80:
                    cur_close = float(df['Close'].iloc[-1])
                    if (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4] >= 0.20:
                        res_20pct.append({"代號": s.replace(".TW", ""), "現價": cur_close})
                    if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                        res_high.append({"代號": s.replace(".TW", ""), "現價": cur_close})
            
            # 冷卻時間
            time.sleep(random.uniform(5, 8))
        except:
            continue
            
    return pd.DataFrame(res_20pct), pd.DataFrame(res_high)

# --- 介面 ---
st.title("🔥 台股精準策略掃描")
min_vol = st.number_input("最低成交量 (張)", value=500)

# 使用簡單的按鈕觸發
if st.button("啟動掃描"):
    # 為了測試穩定性，建議先用一小部分代碼，之後再全掃
    # 這裡放你要掃描的完整清單 (你原本的 get_all_tickers)
    tickers = [f"{i:04d}.TW" for i in range(1100, 2000)] # 先掃這 900 檔
    
    df20, dfH = run_scanner(tickers, min_vol)
    
    st.subheader("🚀 指標 + 3天漲20%")
    st.dataframe(df20, width=1000)
    
    st.subheader("📈 指標 + 半年新高")
    st.dataframe(dfH, width=1000)
