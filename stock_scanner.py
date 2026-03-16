import streamlit as st
import pandas as pd
import yfinance as yf
import time
import random
import requests
import urllib3
from ta.momentum import StochasticOscillator

# 1. 環境設定：隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(page_title="台股全市場飆股掃描器", layout="wide")

@st.cache_data(ttl=86400)
def get_all_tickers():
    """獲取上市所有個股清單"""
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=15)
    df = pd.read_html(resp.text)[0]
    # 正規表達式篩選 4 位數代號
    df = df[df.iloc[:, 0].str.match(r'^\d{4}\s', na=False)]
    return [f"{t.split()[0]}.TW" for t in df.iloc[:, 0]]

def scan_full_market(all_tickers):
    """執行全市場分批掃描"""
    results = []
    batch_size = 30 # 每批次 30 檔，平衡速度與穩定性
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {min((i+1)*batch_size, len(all_tickers))} / {len(all_tickers)} 檔")
        
        try:
            # 啟用多執行緒 threads=True
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 20: continue
                
                # 指標計算
                vol_20ma = df['Volume'].rolling(20).mean().iloc[-1]
                if vol_20ma == 0: continue
                vol_ratio = df['Volume'].iloc[-1] / vol_20ma
                
                # 計算 K 值
                stoch = StochasticOscillator(df['High'], df['Low'], df['Close'], window=9)
                k = float(stoch.stoch().iloc[-1])
                
                # 篩選飆股條件：量比 > 1.5 且 K > 75
                if vol_ratio > 1.5 and k > 75:
                    results.append({
                        "代號": ticker.replace(".TW", ""), 
                        "量比": round(float(vol_ratio), 2), 
                        "K值": round(k, 2)
                    })
            
            # 每批次後強制冷卻，保護 API 連線品質
            time.sleep(random.uniform(5, 8))
            
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results)

# --- UI 渲染 ---
st.title("📊 台股全市場飆股掃描器 (進階版)")
if st.button("啟動全市場掃描"):
    with st.spinner("正在掃描 1700+ 檔股票，這大約需要 5-10 分鐘，請勿關閉網頁..."):
        all_tickers = get_all_tickers()
        df_res = scan_full_market(all_tickers)
        
        if not df_res.empty:
            st.success(f"掃描完成！共發現 {len(df_res)} 檔符合標的。")
            st.dataframe(df_res.sort_values("量比", ascending=False), use_container_width=True)
            
            # 加入 CSV 下載功能
            csv = df_res.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 下載掃描結果 CSV", data=csv, file_name='market_scan_results.csv', mime='text/csv')
        else:
            st.warning("掃描完畢，目前市場無符合飆股條件的標的。")
