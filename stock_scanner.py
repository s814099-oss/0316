import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator
from bs4 import BeautifulSoup

# 1. 環境設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

@st.cache_data(ttl=86400)
def get_all_tickers():
    urls = {
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2": "TW",  # 上市
        "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4": "TWO" # 上櫃
    }
    all_tickers = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    for url, suffix in urls.items():
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=20)
            resp.encoding = 'big5'
            
            # 使用 BeautifulSoup 確保鎖定表格，解決 No tables found 問題
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table', {'class': 'h4'})
            
            if table:
                df = pd.read_html(str(table))[0]
            else:
                df_list = pd.read_html(resp.text)
                df = df_list[0] if df_list else None
            
            if df is not None:
                # 篩選四位數代號的股票
                symbols = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)].iloc[:, 0]
                all_tickers.extend([f"{s.split()[0]}.{suffix}" for s in symbols])
        except Exception as e:
            st.warning(f"掃描來源時發生輕微錯誤 (跳過該分組): {e}")
            continue
            
    return list(set(all_tickers))

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 分批下載以提升穩定性
    batch_size = 25
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"進度: {i+1}/{len(batches)} 批次 | 目前掃描: {batch[0]}...")
        
        try:
            # 使用 threads=True 加速，配合隨機延遲保護 IP
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=15)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 30: continue
                
                # 回溯檢查最近 7 天的訊號
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    # 1. 單位換算：成交量(張)
                    vol_in_thousands = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_in_thousands < 5000: continue
                    
                    # 2. 指標計算
                    ma5 = df_sub['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
                    ma20 = df_sub['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
                    vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9, fillna=True)
                    k = float(stoch.stoch().iloc[-1])
                    
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        latest_close = float(df['Close'].iloc[-1]) # 獲取今日最新價格
                        
                        # 策略 A: 短線噴出 (3天漲幅 > 20%)
                        if idx <= -4:
                            prev_close = float(df['Close'].iloc[idx-3])
                            three_day_gain = (float(df['Close'].iloc[idx]) - prev_close) / prev_close
                            if three_day_gain > 0.20:
                                results_3day.append({
                                    "代號": ticker.split('.')[0], 
                                    "訊號日期": signal_date, 
                                    "最新現價": round(latest_close, 2), 
                                    "漲幅": f"{three_day_gain:.1%}", 
                                    "量比": round(vol_ratio, 2), 
                                    "成交量(張)": int(vol_in_thousands)
                                })
                        
                        # 策略 B: 中線突破 (半年新高)
                        six_mo_high = df['Close'].rolling(120, min_periods=1).max().iloc[-1]
                        if float(df['Close'].iloc[idx]) >= six_mo_high:
                            results_6mo.append({
                                "代號": ticker.split('.')[0], 
                                "訊號日期": signal_date, 
                                "最新現價": round(latest_close, 2), 
                                "半年高點": round(six_mo_high, 2), 
                                "量比": round(vol_ratio, 2), 
                                "成交量(張)": int(vol_in_thousands)
                            })
                        break 
            time.sleep(random.uniform(1.0, 1.8)) # 保護性延遲
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# 3. UI 介面
st.title("📊 終極版台股飆股掃描器 (上市+上櫃)")

if st.button("啟動全市場掃描"):
    with st.spinner("正在抓取清單並分析數據..."):
        all_tickers = get_all_tickers()
        df_3day, df_6mo = scan_full_market(all_tickers)
        
        st.info(f"✅ 掃描完成！總共分析了 {len(all_tickers)} 檔上市櫃股票。")
        
        tab1, tab2 = st.tabs(["🚀 短線噴出策略", "📈 中線突破策略"])
        
        with tab1:
            st.subheader("訊號：3天漲幅 > 20% + 爆量強勢")
            st.dataframe(df_3day, use_container_width=True)
            
        with tab2:
            st.subheader("訊號：創半年新高 + 爆量強勢")
            st.dataframe(df_6mo, use_container_width=True)
