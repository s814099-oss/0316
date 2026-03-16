import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股飆股掃描器 (含價格驗證)", layout="wide")

def scan_stocks():
    # 限制掃描 100 檔最熱門標的，避開 Yahoo 封鎖限制，確保資料精準
    target_stocks = ["2330.TW", "2454.TW", "2317.TW", "2303.TW", "2603.TW", "2382.TW", "3008.TW", "2357.TW", "2308.TW", "3017.TW", "6669.TW", "3661.TW", "2345.TW", "2609.TW", "2610.TW"]
    
    results = []
    st.write(f"正在掃描 {len(target_stocks)} 檔高流動性個股...")
    progress = st.progress(0)
    
    for i, s in enumerate(target_stocks):
        progress.progress(i / len(target_stocks))
        try:
            # 引入緩衝，避開 Rate Limit
            time.sleep(random.uniform(0.3, 0.8))
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            # 扁平化 Multi-Index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if df.empty or len(df) < 30: continue
            
            # 獲取價格與指標
            price = float(df['Close'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = float(vol5 / vol20)
            
            # 條件計算
            k_val = float(StochasticOscillator(df['High'], df['Low'], df['Close']).stoch().iloc[-1])
            
            # 篩選條件
            if vol_ratio > 0.5 and k_val > 28:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "當前價格": round(price, 2),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except: continue
            
    progress.empty()
    return pd.DataFrame(results)

st.title("🔥 台股噴發掃描器 (數據驗證版)")
if st.button("執行驗證掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res, use_container_width=True)
        st.success("價格已同步顯示，你可以直接對照券商軟體確認！")
    else:
        st.warning("無符合條件標的。")
