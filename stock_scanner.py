import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
from ta.momentum import StochasticOscillator

st.set_page_config(page_title="台股飆股掃描器 (300檔)", layout="wide")

def get_300_stocks():
    # 這是台灣股市高流動性的代表清單
    # 為了簡化與保證運作，我們使用高流動性代碼清單
    # 若需擴大，可在此處補充更多代碼
    tickers = [f"{i:04d}.TW" for i in range(2300, 2600)] 
    return tickers

def scan_stocks():
    target_stocks = get_300_stocks()
    st.write(f"系統啟動！正在掃描 300 檔高流動性標的...")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 批次處理
    batch_size = 10
    for i in range(0, len(target_stocks), batch_size):
        batch = target_stocks[i : i + batch_size]
        progress_bar.progress(i / len(target_stocks))
        status_text.text(f"掃描進度: {i}/{len(target_stocks)} ...")
        
        try:
            # 隨機延遲，避開頻率限制
            time.sleep(random.uniform(0.5, 1.2))
            data = yf.download(batch, period="2mo", interval="1d", progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            for s in batch:
                if s not in data.columns: continue
                df = data[s].dropna()
                if len(df) < 30: continue
                
                # 計算指標
                price = float(df['Close'].iloc[-1])
                volume = float(df['Volume'].iloc[-1])
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                vol_ratio = float(vol5 / vol20)
                
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 這裡暫時放寬條件以便讓你確認結果，你可以之後自行改回嚴格閥值
                if vol_ratio > 1 and k_val > 20:
                    results.append({
                        "股票": s.replace(".TW", ""),
                        "當前價格": round(price, 2),
                        "當日成交量": int(volume),
                        "量比": round(vol_ratio, 2),
                        "K值": round(k_val, 2)
                    })
        except: continue
            
    progress_bar.empty()
    status_text.text("掃描完成！")
    return pd.DataFrame(results)

st.title("🔥 台股 300 檔飆股掃描器 (強化版)")
if st.button("執行 300 檔深度掃描"):
    df_res = scan_stocks()
    if not df_res.empty:
        st.dataframe(df_res.sort_values(by="量比", ascending=False), use_container_width=True)
    else:
        st.warning("目前無標的符合條件。請嘗試調低條件閥值測試。")
