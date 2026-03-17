import streamlit as st
import pandas as pd
import yfinance as yf
import time
import requests
import urllib3
import random
from ta.momentum import StochasticOscillator

# 1. 核心設定：關閉 SSL 憑證警告（解決你之前的 SSL Error）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
st.set_page_config(layout="wide", page_title="台股飆股掃描器-精準版")

@st.cache_data(ttl=86400)
def get_all_tickers():
    """精準抓取上市櫃名單，繞過憑證檢查"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0'}
    all_tickers = []
    
    # A. 抓取上市清單 (TWSE) - 強制跳過 SSL 驗證
    try:
        twse_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_AVG_ALL?response=json"
        resp = requests.get(twse_url, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get('data', [])
            all_tickers.extend([f"{item[0]}.TW" for item in data if len(item[0]) == 4])
    except Exception as e:
        st.warning(f"上市清單抓取失敗（跳過）: {e}")

    # B. 抓取上櫃清單 (TPEx) - 強制跳過 SSL 驗證
    try:
        tpex_url = "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/otc_quotes_no1430_result.php?l=zh-tw"
        resp = requests.get(tpex_url, headers=headers, verify=False, timeout=15)
        if resp.status_code == 200:
            data = resp.json().get('aaData', [])
            all_tickers.extend([f"{item[0]}.TWO" for item in data if len(item[0]) == 4])
    except Exception as e:
        st.warning(f"上櫃清單抓取失敗（跳過）: {e}")

    # 如果都失敗，才使用保底清單
    if not all_tickers:
        return ["2330.TW", "2317.TW", "2454.TW", "2603.TW", "2303.TW", "2609.TW"]
        
    return list(set(all_tickers))

def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 批次量設為 20，避免 Yahoo 偵測為攻擊
    batch_size = 20
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {i+1}/{len(batches)} 批次 | 當前處理: {batch[0]}")
        
        try:
            # 下載數據，threads=True 加速
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=15)
            
            for ticker in batch:
                # 確保有資料才處理
                if ticker not in data or data[ticker].empty: continue
                df = data[ticker]
                if len(df) < 30: continue
                
                # --- 篩選邏輯：回溯 7 天尋找訊號 ---
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    # 1. 量能過濾 (成交量 > 5000 張)
                    vol_now = float(df_sub['Volume'].iloc[-1]) / 1000
                    if vol_now < 5000: continue
                    
                    # 2. 技術指標計算 (量比與 K 值)
                    ma5_v = df_sub['Volume'].rolling(5).mean().iloc[-1]
                    ma20_v = df_sub['Volume'].rolling(20).mean().iloc[-1]
                    vol_ratio = ma5_v / ma20_v if ma20_v > 0 else 0
                    
                    stoch = StochasticOscillator(df_sub['High'], df_sub['Low'], df_sub['Close'], window=9, fillna=True)
                    k_val = float(stoch.stoch().iloc[-1])
                    
                    # 策略門檻：K值 > 80 且量比 > 1.85
                    if k_val > 80 and vol_ratio > 1.85:
                        sig_date = df.index[idx].strftime('%Y-%m-%d')
                        curr_price = round(float(df['Close'].iloc[-1]), 2)
                        
                        # A. 短線噴出 (3天 > 20%)
                        if idx <= -4:
                            p_start = float(df['Close'].iloc[idx-3])
                            gain = (float(df['Close'].iloc[idx]) - p_start) / p_start
                            if gain > 0.20:
                                results_3day.append({
                                    "代號": ticker.split('.')[0], "訊號日": sig_date, 
                                    "現價": curr_price, "3日漲幅": f"{gain:.1%}", 
                                    "量比": round(vol_ratio, 2), "張數": int(vol_now)
                                })
                        
                        # B. 中線突破 (半年高點)
                        h_6m = df['Close'].rolling(120, min_periods=1).max().iloc[-1]
                        if float(df['Close'].iloc[idx]) >= h_6m:
                            results_6mo.append({
                                "代號": ticker.split('.')[0], "訊號日": sig_date, 
                                "現價": curr_price, "半年高點": round(h_6m, 2), 
                                "量比": round(vol_ratio, 2), "張數": int(vol_now)
                            })
                        break 
            # 增加隨機延遲保護 IP
            time.sleep(random.uniform(1.5, 2.5))
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)

# 3. 網頁 UI
st.title("📊 台股飆股掃描器 (精準 API 版)")
st.caption("自動繞過 SSL 驗證與頻率限制，掃描全台股上市櫃股票。")

if st.button("啟動全市場掃描"):
    with st.spinner("正在獲取最新清單並分析量能指標..."):
        all_tickers = get_all_tickers()
        df_3d, df_6m = scan_full_market(all_tickers)
        
        st.success(f"掃描完成！本次共分析 {len(all_tickers)} 檔有效標的。")
        
        t1, t2 = st.tabs(["🚀 短線強勢噴出", "📈 中線高點突破"])
        with t1:
            st.dataframe(df_3d, use_container_width=True)
        with t2:
            st.dataframe(df_6m, use_container_width=True)
