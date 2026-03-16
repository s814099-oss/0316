import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator
import datetime

st.set_page_config(page_title="台股飆股掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_all_stocks():
    codes = []
    for mode in ["2", "4"]:
        try:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
            res = requests.get(url, timeout=10)
            df = pd.read_html(res.text)[0]
            for item in df.iloc[:, 0]:
                match = re.match(r'^(\d{4})\s+', str(item))
                if match: codes.append(f"{match.group(1)}.TW")
        except: continue
    return list(set(codes))

def scan_stocks():
    stocks = get_all_stocks()
    target_stocks = stocks[:300]  # 限制數量避免記憶體溢出
    results = []
    
    st.write(f"正在掃描 {len(target_stocks)} 檔股票...")
    progress = st.progress(0)
    
    for i, s in enumerate(target_stocks):
        progress.progress(i / len(target_stocks))
        try:
            # 強制下載單檔數據，並避免 Multi-Index 問題
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            # --- 關鍵修正：解決 Series 歧義 ---
            # 如果下載到的資料是 Multi-Index (欄位是巢狀的)，將其壓平
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            if df.empty or len(df) < 30: continue
            
            # 計算指標
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            if vol20 == 0: continue
            vol_ratio = float(vol5 / vol20)
            
            close_now = float(df['Close'].iloc[-1])
            close_3 = float(df['Close'].iloc[-4])
            return3 = (close_now - close_3) / close_3
            
            limit_up_sum = (df['Close'].pct_change() >= 0.098).rolling(3).sum().iloc[-1]
            
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # --- 嚴格邏輯條件 ---
            if vol_ratio > 1.85 and (return3 > 0.20 or limit_up_sum >= 2) and k_val > 80:
                results.append({
                    "股票": s.replace(".TW", ""),
                    "價格": round(close_now, 2),
                    "量比": round(vol_ratio, 2),
                    "3日漲幅%": round(return3 * 100, 2),
                    "K值": round(k_val, 2)
                })
        except Exception:
            continue
            
    progress.empty()
    return pd.DataFrame(results)

st.title("🔥 台股噴發掃描器 (最終修正版)")
if st.button("開始執行掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res, use_container_width=True)
    else:
        st.warning("目前市場無符合標的。這代表沒有股票同時滿足：量比>1.85、漲幅>20%、KD>80。")
