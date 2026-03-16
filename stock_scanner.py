import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
import requests
from ta.momentum import StochasticOscillator
from datetime import datetime, timedelta

# 強制繞過 SSL 憑證檢查
ssl._create_default_https_context = ssl._create_unverified_context

st.set_page_config(page_title="台股全市場掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = ["https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"]
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_tickers = []
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=10)
            df = pd.read_html(resp.text)[0]
            df = df.iloc[1:, [0]]
            df.columns = ['代號名稱']
            df['代號'] = df['代號名稱'].str.extract(r'^(\d{4})\s')
            all_tickers.extend([f"{t}.TW" for t in df['代號'].dropna().unique()])
        except: continue
    return list(set(all_tickers))

def run_scanner(tickers, min_vol, v_ratio_limit, k_limit):
    results = []
    total_count = len(tickers) # 總掃描目標數
    
    # UI 佔位符
    progress_bar = st.progress(0)
    status_text = st.empty()
    timer_text = st.empty()
    metric_placeholder = st.empty() # 用於顯示總數
    
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    total_batches = len(batches)
    
    # 顯示總掃描標的數
    metric_placeholder.metric("掃描目標總數", total_count)
    
    for i, batch in enumerate(batches):
        # 計算預估剩餘時間
        remaining_batches = total_batches - i
        eta = datetime.now() + timedelta(seconds=remaining_batches * 2.5)
        
        progress_bar.progress((i + 1) / total_batches)
        status_text.text(f"掃描進度: {min((i+1)*batch_size, total_count)} / {total_count} 檔")
        timer_text.info(f"⏱️ 預計結束時間: {eta.strftime('%H:%M:%S')}")
        
        try:
            time.sleep(random.uniform(1.5, 2.5))
            data = yf.download(batch, period="2mo", interval="1d", progress=False, group_by='ticker', threads=True)
            
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 25: continue
                
                current_vol = float(df['Volume'].iloc[-1])
                if current_vol < (min_vol * 1000): continue
                
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
        except Exception as e:
            if "Rate limited" in str(e):
                time.sleep(30)
                continue
    
    # 掃描完成後清理介面
    timer_text.empty()
    status_text.empty()
    return pd.DataFrame(results)

# --- UI 介面 ---
st.title("📊 台股全市場飆股掃描器")
st.sidebar.header("篩選參數")
min_vol = st.sidebar.number_input("最低成交量 (張)", value=500)
v_ratio = st.sidebar.slider("量比條件", 1.0, 3.0, 1.5)
k_val_limit = st.sidebar.slider("K值門檻", 50, 95, 75)

if st.button("啟動掃描"):
    all_tickers = get_all_tickers()
    if all_tickers:
        df_res = run_scanner(all_tickers, min_vol, v_ratio, k_val_limit)
        if not df_res.empty:
            st.success(f"掃描完成！共發現 {len(df_res)} 檔符合條件標的。")
            st.dataframe(df_res.sort_values("量比", ascending=False), use_container_width=True)
        else:
            st.warning("掃描完畢，無符合條件標的。")
