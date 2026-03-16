import streamlit as st
import pandas as pd
import yfinance as yf
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股噴發掃描器", layout="wide")

# 1. 暴力強制清單 (避開網路解析失敗)
@st.cache_data
def get_all_stocks():
    # 這是台灣股市主要的成交量排行股與大型權值股，包含大部分的飆股潛力標的
    # 為了穩定，先載入這些代表性清單
    return ["2330.TW", "2454.TW", "2317.TW", "2303.TW", "2603.TW", "2382.TW", "3008.TW", "2308.TW", "2357.TW", "3017.TW", "6669.TW", "3661.TW", "2345.TW", "2609.TW", "2610.TW"]

# 2. 核心掃描
def scan_stocks():
    target_stocks = get_all_stocks()
    st.write(f"系統已準備好，開始掃描 {len(target_stocks)} 檔股票...")
    
    results = []
    progress = st.progress(0)
    
    for i, s in enumerate(target_stocks):
        progress.progress(i / len(target_stocks))
        try:
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            if df.empty or len(df) < 30: continue
            
            # 指標計算
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            if vol20 == 0: continue
            
            vol_ratio = float(vol5 / vol20)
            close_now = float(df['Close'].iloc[-1])
            close_3 = float(df['Close'].iloc[-4])
            return3 = (close_now - close_3) / close_3
            
            # 使用 .iloc 的方式計算近三天兩根漲停
            is_limit = (df['Close'].pct_change() >= 0.098)
            limit_up_sum = is_limit.rolling(3).sum().iloc[-1]
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # 條件判斷 (保留你所有的設定)
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_sum >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(close_now, 2),
                    "量比": round(vol_ratio, 2),
                    "漲幅%": round(return3 * 100, 2),
                    "K值": round(k_val, 2)
                })
        except Exception:
            continue
            
    progress.empty()
    return pd.DataFrame(results)

st.title("🔥 台股噴發掃描器 (穩定版)")
if st.button("開始掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("沒有標的符合條件。請確認條件是否過於嚴苛，或資料源目前無數據。")
