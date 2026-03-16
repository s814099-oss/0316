import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import re
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="除錯版 600 檔掃描", layout="wide")

@st.cache_data(ttl=86400)
def get_all_stocks():
    # 強制清單，避免網路抓取失敗
    # 這裡放 600 檔以內的範例代碼，確保清單一定有東西
    return [f"{i:04d}.TW" for i in range(2300, 2900)]

def scan_stocks():
    target_stocks = get_all_stocks()
    st.write(f"系統啟動！準備掃描 {len(target_stocks)} 檔股票...")
    
    results = []
    progress = st.progress(0)
    
    # 這裡將 batch_size 縮小為 1，並加入 print 除錯
    for i, s in enumerate(target_stocks):
        progress.progress(i / len(target_stocks))
        
        try:
            # 這是最關鍵的一步：單檔下載
            df = yf.download(s, period="2mo", interval="1d", progress=False)
            
            # 如果這行沒過，代表是網路問題
            if df.empty:
                continue 
            
            # 修正 Multi-Index
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # 指標計算
            vol5 = df['Volume'].rolling(5).mean().iloc[-1]
            vol20 = df['Volume'].rolling(20).mean().iloc[-1]
            
            # 這裡顯示目前掃到的代碼，證明它正在運作
            st.write(f"正在分析: {s} | 量比: {round(float(vol5/vol20), 2)}")
            
            # ... 後續條件判斷 (省略以保持篇幅) ...
            
        except Exception as e:
            st.error(f"掃描 {s} 時發生錯誤: {e}")
            continue

    return pd.DataFrame(results)

if st.button("開始執行 600 檔"):
    df_res = scan_stocks()
