import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股飆股掃描器 (穩定版)", layout="wide")

# 1. 確保只有有效代碼
def get_valid_stocks():
    # 這裡放目前台股熱門且確定存在的代碼
    # 若要擴充，只需將更多代碼加入此 list
    tickers = ["2330.TW", "2317.TW", "2454.TW", "2303.TW", "2603.TW", "2382.TW", "3008.TW", "2308.TW", "2357.TW", "3017.TW", 
               "2345.TW", "2609.TW", "2610.TW", "2409.TW", "2448.TW", "2881.TW", "2882.TW", "2891.TW", "2885.TW", "2886.TW"]
    return tickers

# 2. 核心掃描功能
def scan_stocks():
    target_stocks = get_valid_stocks()
    st.write(f"系統準備中，開始掃描 {len(target_stocks)} 檔標的...")
    
    results = []
    progress_bar = st.progress(0)
    
    for i, s in enumerate(target_stocks):
        progress_bar.progress((i + 1) / len(target_stocks))
        try:
            # 隨機延遲保護連線
            time.sleep(random.uniform(0.5, 1.0))
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if df.empty or len(df) < 30: continue
            
            # 計算指標
            price = float(df['Close'].iloc[-1])
            volume = float(df['Volume'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            if vol20 == 0: continue
            vol_ratio = float(vol5 / vol20)
            
            # 這裡示範計算 K 值
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # 條件：這裡為了確保你有資料看，預設放寬到 vol_ratio > 0.8
            if vol_ratio > 0.8 and k_val > 50:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "當前價格": round(price, 2),
                    "成交量": int(volume),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except Exception:
            continue
            
    progress_bar.empty()
    return pd.DataFrame(results)

# 3. 介面呈現
st.title("🔥 台股噴發掃描器 (最終版)")
if st.button("執行掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res.sort_values(by="量比", ascending=False), use_container_width=True)
    else:
        st.warning("無符合條件標的，請嘗試調低條件閾值。")
