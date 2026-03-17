import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

# 1. 基礎設定
st.set_page_config(layout="wide", page_title="台股飆股與突破掃描器")

@st.cache_data(ttl=86400)
def get_all_tickers():
    """使用最穩定的 GitHub 備份清單，徹底避開證交所 SSL 與解析錯誤"""
    try:
        # 這裡直接從公開整理好的 GitHub 抓取台灣股票清單
        # 如果這個暫時失效，我們有保底邏輯
        url = "https://raw.githubusercontent.com/finmind/finmind-data/master/data/stock_info.csv"
        df = pd.read_csv(url)
        
        # 篩選台股 (台灣市場) 且代號為 4 位數的股票
        # 這裡會包含上市 (.TW) 與 上櫃 (.TWO)
        df = df[df['stock_id'].str.len() == 4]
        
        all_tickers = []
        for _, row in df.iterrows():
            suffix = ".TW" if row['market_type'] == 'P' else ".TWO"
            all_tickers.append(f"{row['stock_id']}{suffix}")
            
        return list(set(all_tickers))
    except:
        # 最終保底清單：如果網路真的斷了，至少還有這些熱門股可以跑
        return ["2330.TW", "2317.TW", "2454.TW", "2303.TW", "2603.TW", "2609.TW", "2615.TW", "2308.TW"]

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 批次處理量，30 檔一組是 Yahoo 的甜蜜點
    batch_size = 30
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {i+1}/{len(batches)} 批次 | 當前處理: {batch[0]}")
        
        try:
            # 這裡用 threads=True 加速
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=20)
            
            for ticker in batch:
                # 處理單一或多個回傳格式
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
                    
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        latest_close = float(df['Close'].iloc[-1])
                        
                        # 策略 A: 短線噴出
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
                        
                        # 策略 B: 中線突破
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
            time.sleep(random.uniform(1.2, 1.8))
        except:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# 3. UI 介面
st.title("📊 台股飆股掃描器 (穩定終極版)")

if st.button("啟動全市場掃描"):
    with st.spinner("正在獲取清單並開始掃描..."):
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
