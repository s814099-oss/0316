import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 1. 基礎設定
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

@st.cache_data(ttl=86400)
def get_all_tickers():
    """使用官方 JSON API 抓取清單，避開網頁爬蟲被擋的問題"""
    all_tickers = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        # A. 抓取上市股票 (TWSE API)
        twse_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG_ALL?response=json"
        resp = requests.get(twse_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if 'data' in data:
                all_tickers.extend([f"{item[0]}.TW" for item in data['data'] if len(item[0]) == 4])
        
        # B. 抓取上櫃股票 (TPEx API)
        tpex_url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_result.php?l=zh-tw"
        resp = requests.get(tpex_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if 'aaData' in data:
                all_tickers.extend([f"{item[0]}.TWO" for item in data['aaData'] if len(item[0]) == 4])
                
    except Exception as e:
        st.error(f"清單抓取失敗: {e}")
        # 保底方案：至少能跑這幾檔
        return ["2330.TW", "2317.TW", "2454.TW", "2303.TW", "2603.TW"]
            
    return list(set(all_tickers))

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 批次處理，降低被 Yahoo 阻擋機率
    batch_size = 25
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {i+1}/{len(batches)} 批次 | 當前處理: {batch[0]}")
        
        try:
            # 下載半年數據
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=20)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 30: continue
                
                # 回溯 7 天尋找符合條件的訊號
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
                    
                    # 條件：爆量且強勢
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        latest_close = float(df['Close'].iloc[-1]) # 最新收盤價
                        
                        # A 策略: 短線噴出
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
                        
                        # B 策略: 中線突破
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
            time.sleep(random.uniform(1.2, 2.0))
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# 3. UI 介面
st.title("📊 終極版台股飆股掃描器 (API版)")

if st.button("啟動全市場掃描"):
    with st.spinner("正在連接 API 並抓取全市場清單..."):
        all_tickers = get_all_tickers()
        df_3day, df_6mo = scan_full_market(all_tickers)
        
        st.info(f"✅ 掃描完成！本次掃描範圍：{len(all_tickers)} 檔上市櫃股票。")
        
        tab1, tab2 = st.tabs(["🚀 短線噴出策略", "📈 中線突破策略"])
        
        with tab1:
            st.subheader("符合：3天內漲幅 > 20% + 爆量 (張數 > 5000)")
            st.dataframe(df_3day, use_container_width=True)
            
        with tab2:
            st.subheader("符合：創半年新高 + 爆量 (張數 > 5000)")
            st.dataframe(df_6mo, use_container_width=True)
