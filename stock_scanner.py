import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator

# 強制繞過 SSL 憑證檢查
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="台股全市場飆股掃描器", layout="wide")

# 1. 抓取上市與上櫃所有代碼
@st.cache_data(ttl=86400)
def get_all_tickers():
    # 上市 (strMode=2) 與 上櫃 (strMode=4)
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
            # 提取 4 碼數字
            df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
            tickers = df['代號'].dropna().unique().tolist()
            all_tickers.extend([f"{t}.TW" for t in tickers])
        except Exception as e:
            st.error(f"清單獲取失敗 ({url}): {e}")
    
    return list(set(all_tickers)) # 移除重複項

# 2. 核心掃描運算
def run_scanner(tickers, min_volume):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    
    for i, s in enumerate(tickers):
        progress_bar.progress((i + 1) / total)
        if i % 10 == 0:
            status_text.text(f"掃描進度: {i+1}/{total} | 正在檢查: {s}")
        
        try:
            # 降低延遲以加快速度，但仍保留基本間隔防止封鎖
            time.sleep(0.05) 
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 25: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # --- 獲取數據 ---
            current_vol = float(df['Volume'].iloc[-1])
            # 過濾量太少的標的 (1,000張 = 1,000,000 股)
            if current_vol < (min_volume * 1000):
                continue
            
            price = float(df['Close'].iloc[-1])
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            if vol20 == 0: continue
            vol_ratio = vol5 / vol20
            
            # KD 指標
            stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
            k_val = float(stoch.stoch().iloc[-1])
            
            # --- 核心篩選條件 ---
            if vol_ratio > 1.85 and k_val > 80:
                results.append({
                    "代號": s.replace(".TW", ""),
                    "現價": round(price, 2),
                    "今日成交量(張)": int(current_vol / 1000),
                    "量比": round(vol_ratio, 2),
                    "K值": round(k_val, 2)
                })
        except:
            continue
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(results)

# 3. 介面
st.title("🔥 台股全市場飆股掃描器 (流動性加強版)")

# 使用者自訂過濾量
vol_limit = st.sidebar.number_input("最低成交量過濾 (張)", value=1000, step=100)
ratio_limit = st.sidebar.slider("量比條件 (5日/20日)", 1.0, 3.0, 1.85)
k_limit = st.sidebar.slider("K值條件", 50, 95, 80)

if st.button("執行全市場掃描"):
    tickers = get_all_tickers()
    if tickers:
        df_res = run_scanner(tickers, vol_limit)
        
        if not df_res.empty:
            st.success(f"掃描完畢！符合條件且成交量大於 {vol_limit} 張的標的如下：")
            st.dataframe(
                df_res.sort_values(by="量比", ascending=False), 
                use_container_width=True
            )
        else:
            st.warning(f"掃描結束。無符合條件之標的 (成交量 > {vol_limit}張, 量比 > {ratio_limit}, K > {k_limit})")
    else:
        st.error("清單載入失敗。")
