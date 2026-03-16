import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import ssl
from ta.momentum import StochasticOscillator
from datetime import datetime, timedelta

ssl._create_default_https_context = ssl._create_unverified_context
st.set_page_config(page_title="台股三策略分批掃描", layout="wide")

# 這裡放入你原本的 get_all_tickers 函數 (略)
# ... (為了簡潔我省略了這部分)

def run_scanner_stable(tickers, min_vol):
    res_explosion = [] # 量比>1.85 & K>80 & 3天漲20%
    res_breakout = []  # 量比>1.85 & K>80 & 半年新高
    
    # 關鍵：強制分批，確保穩定性
    batch_size = 20
    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    
    for i, batch in enumerate(batches):
        # 顯示進度
        progress_bar.progress((i + 1) / len(batches))
        elapsed = time.time() - start_time
        eta = (len(batches) - (i + 1)) * (elapsed / (i + 1))
        status_text.text(f"分批掃描中: {i+1}/{len(batches)} 批次 | 預計結束: {str(timedelta(seconds=int(eta)))}")
        
        try:
            # 每一批次下載前都休息一下，防止被封鎖
            time.sleep(random.uniform(2.0, 3.5))
            
            # 使用 group_by='ticker' 一次取 20 檔
            data = yf.download(batch, period="6mo", interval="1d", progress=False, group_by='ticker', threads=True)
            
            for s in batch:
                if s not in data or data[s].empty: continue
                df = data[s].dropna()
                if len(df) < 120: continue 
                
                # 成交量過濾
                if float(df['Volume'].iloc[-1]) < (min_vol * 1000): continue
                
                # 計算指標
                vol5 = df['Volume'].rolling(5).mean().iloc[-1]
                vol20 = df['Volume'].rolling(20).mean().iloc[-1]
                if vol20 == 0: continue
                vol_ratio = vol5 / vol20
                
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9, smooth_window=3)
                k_val = float(stoch.stoch().iloc[-1])
                
                # 策略門檻：必須同時符合量比與 KD
                if vol_ratio > 1.85 and k_val > 80:
                    cur_close = float(df['Close'].iloc[-1])
                    
                    # 條件 A: 3天漲幅 > 20%
                    three_day_gain = (cur_close - df['Close'].iloc[-4]) / df['Close'].iloc[-4]
                    if three_day_gain >= 0.20:
                        res_explosion.append({"代號": s.replace(".TW", ""), "現價": cur_close, "漲幅": f"{three_day_gain:.2%}", "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
                    
                    # 條件 B: 半年新高
                    if cur_close >= df['High'].rolling(120).max().iloc[-1]:
                        res_breakout.append({"代號": s.replace(".TW", ""), "現價": cur_close, "量比": round(vol_ratio, 2), "K值": round(k_val, 2)})
        
        except Exception as e:
            # 遇到 rate limit 自動休息 45 秒，這很重要
            if "Rate limited" in str(e):
                time.sleep(45)
                continue
            continue
            
    return pd.DataFrame(res_explosion), pd.DataFrame(res_breakout)
