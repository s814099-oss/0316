import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
from ta.momentum import StochasticOscillator

ssl._create_default_https_context = ssl._create_unverified_context

def get_tickers():
    # 簡易取得代號邏輯
    return [f"{i:04d}.TW" for i in range(1100, 9999)] # 根據你過去習慣調整

st.title("極簡版：強勢股篩選器")
min_vol = st.number_input("最低成交量 (張)", value=500)

if st.button("執行篩選"):
    tickers = get_tickers()
    res_20pct = []
    res_high = []
    
    # 核心：每次只處理 10 檔，極低記憶體消耗
    for i in range(0, len(tickers), 10):
        batch = tickers[i:i+10]
        try:
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker')
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 120 or df['Volume'].iloc[-1] < min_vol * 1000: continue
                
                # 計算指標
                vol_ratio = df['Volume'].rolling(5).mean().iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k = float(stoch.stoch().iloc[-1])
                
                if vol_ratio > 1.85 and k > 80:
                    close = float(df['Close'].iloc[-1])
                    # 條件 1
                    if (close - df['Close'].iloc[-4]) / df['Close'].iloc[-4] >= 0.20:
                        res_20pct.append({"代號": s, "現價": close})
                    # 條件 2
                    if close >= df['High'].rolling(120).max().iloc[-1]:
                        res_high.append({"代號": s, "現價": close})
            
            st.write(f"已掃描: {i+10} 檔...")
            time.sleep(2) # 強制緩衝
        except: continue

    st.subheader("🚀 3天漲20% (指標+爆發)")
    st.write(pd.DataFrame(res_20pct))
    st.subheader("📈 半年新高 (指標+突破)")
    st.write(pd.DataFrame(res_high))
