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
    """完全不依賴外部網站，直接生成台股常用代號區間"""
    # 這裡定義台股主要的股票代號區間 (1101~9999)
    # 雖然包含一些無效代號，但 yfinance 下載時會自動過濾，這最穩定
    ranges = [
        (1101, 2000), (2001, 3000), (3001, 4000), (4001, 5000),
        (5001, 6000), (6001, 7000), (8001, 9000), (9901, 9960)
    ]
    
    base_numbers = []
    for start, end in ranges:
        base_numbers.extend([str(i) for i in range(start, end)])
    
    # 產生上市與上櫃兩種後綴
    all_potential = [f"{n}.TW" for n in base_numbers] + [f"{n}.TWO" for n in base_numbers]
    
    # 為了不讓 yfinance 一次負擔太大，我們只回傳這份「潛力清單」
    return all_potential

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 因為清單變大，我們把 batch 調大到 50，提高效率
    batch_size = 50
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    # 計算真正有掃描到的有效股數
    scanned_count = 0
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"進度: {i+1}/{len(batches)} 批次 | 正在檢測區段: {batch[0]}...")
        
        try:
            # 下載數據，timeout 設短一點避免卡死
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=10)
            
            for ticker in batch:
                if ticker not in data or data[ticker].empty:
                    continue
                
                df = data[ticker]
                if len(df) < 30: continue
                
                # 只要有資料，就列入掃描統計
                scanned_count += 1
                
                # --- 你的核心篩選邏輯 ---
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    vol_in_thousands = float(df_sub['Volume'].iloc[-1]) / 1000
                    # 門檻：成交量需 > 5000 張
                    if vol_in_thousands < 5000: continue
                    
                    ma5 = df_sub['Volume'].rolling(5, min_periods=1).mean().iloc[-1]
                    ma20 = df_sub['Volume'].rolling(20, min_periods=1).mean().iloc[-1]
                    vol_ratio = (ma5 / ma20) if ma20 > 0 else 0
                    
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9, fillna=True)
                    k = float(stoch.stoch().iloc[-1])
                    
                    if vol_ratio > 1.85 and k > 80:
                        signal_date = df.index[idx].strftime('%Y-%m-%d')
                        latest_close = float(df['Close'].iloc[-1])
                        
                        if idx <= -4:
                            prev_close = float(df['Close'].iloc[idx-3])
                            three_day_gain = (float(df['Close'].iloc[idx]) - prev_close) / prev_close
                            if three_day_gain > 0.20:
                                results_3day.append({"代號": ticker.split('.')[0], "訊號日期": signal_date, "最新現價": round(latest_close, 2), "漲幅": f"{three_day_gain:.1%}", "量比": round(vol_ratio, 2), "成交量(張)": int(vol_in_thousands)})
                        
                        six_mo_high = df['Close'].rolling(120, min_periods=1).max().iloc[-1]
                        if float(df['Close'].iloc[idx]) >= six_mo_high:
                            results_6mo.append({"代號": ticker.split('.')[0], "訊號日期": signal_date, "最新現價": round(latest_close, 2), "半年高點": round(six_mo_high, 2), "量比": round(vol_ratio, 2), "成交量(張)": int(vol_in_thousands)})
                        break 
            
            # 稍微停頓避免被 Yahoo 封鎖
            time.sleep(0.3)
            
        except:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo), scanned_count

# 3. UI 介面
st.title("📊 終極台股飆股掃描器 (全自動生成版)")

if st.button("啟動全市場掃描"):
    with st.spinner("正在執行全市場掃描，這可能需要幾分鐘..."):
        all_potential = get_all_tickers()
        df_3day, df_6mo, total_scanned = scan_full_market(all_potential)
        
        st.info(f"✅ 掃描完成！總共實際分析了 {total_scanned} 檔有效上市櫃股票。")
        
        tab1, tab2 = st.tabs(["🚀 短線噴出策略", "📈 中線突破策略"])
        with tab1:
            st.dataframe(df_3day, use_container_width=True)
        with tab2:
            st.dataframe(df_6mo, use_container_width=True)
