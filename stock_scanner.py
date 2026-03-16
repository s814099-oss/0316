import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# 強制繞過 SSL 憑證檢查
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股全市場掃描器 (頻率優化版)", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = [
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_tickers = []
    for url in urls:
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=15)
            df = pd.read_html(response.text)[0]
            df = df.iloc[1:, [0]]
            df.columns = ['代號名稱']
            df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
            tickers = df['代號'].dropna().unique().tolist()
            all_tickers.extend([f"{t}.TW" for t in tickers])
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers, min_volume, v_ratio_limit, k_limit):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # --- 關鍵優化：分批處理 (Batch Processing) ---
    batch_size = 50 
    total_batches = (len(tickers) // batch_size) + 1
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        batch_idx = (i // batch_size) + 1
        progress_bar.progress(batch_idx / total_batches)
        status_text.text(f"正在批次下載第 {batch_idx}/{total_batches} 組數據...")
        
        try:
            # 一次下載一整組 50 檔股票的數據
            data = yf.download(batch, period="2mo", interval="1d", progress=False, group_by='ticker')
            
            for s in batch:
                try:
                    # 檢查該代碼是否有數據
                    if s not in data or data[s].empty: continue
                    df = data[s].dropna()
                    if len(df) < 25: continue
                    
                    # 獲取成交量並過濾 (張數 * 1000 = 股數)
                    current_vol = float(df['Volume'].iloc[-1])
                    if current_vol < (min_volume * 1000): continue
                    
                    price = float(df['Close'].iloc[-1])
                    vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                    vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                    if vol20 == 0: continue
                    vol_ratio = vol5 / vol20
                    
                    stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                    k_val = float(stoch.stoch().iloc[-1])
                    
                    if vol_ratio > v_ratio_limit and k_val > k_limit:
                        results.append({
                            "代號": s.replace(".TW", ""),
                            "現價": round(price, 2),
                            "今日張數": int(current_vol / 1000),
                            "量比": round(vol_ratio, 2),
                            "K值": round(k_val, 2)
                        })
                except: continue
            
            # 批次間稍微休息，避免被盯上
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            st.warning(f"批次下載中斷: {e}")
            time.sleep(10) # 遇到錯誤休息久一點
            continue
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

st.title("🚀 台股全市場飆股掃描器 (專業穩定版)")

st.sidebar.header("篩選參數")
vol_limit = st.sidebar.number_input("最低成交量 (張)", value=1000)
ratio_limit = st.sidebar.slider("量比 (5MA/20MA)", 1.0, 3.0, 1.85)
k_limit = st.sidebar.slider("K值門檻", 50, 95, 80)

if st.button("啟動全市場掃描"):
    all_tickers = get_all_tickers()
    if all_tickers:
        df_res = run_scanner(all_tickers, vol_limit, ratio_limit, k_limit)
        if not df_res.empty:
            st.success(f"掃描完畢！符合條件標的：")
            st.dataframe(df_res.sort_values(by="量比", ascending=False), use_container_width=True)
        else:
            st.warning("無符合條件標的，請嘗試放寬參數。")
