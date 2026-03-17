@st.cache_data(ttl=86400)
def get_all_tickers():
    """不再依賴外部清單 API，直接生成台股所有可能的 4 位數代號，徹底解決 SSL 報錯"""
    # 台股絕大多數股票都是 4 位數
    base_numbers = [str(i) for i in range(1101, 9999)]
    
    # 同時產生上市(.TW)與上櫃(.TWO)的候選名單
    tw_list = [f"{n}.TW" for n in base_numbers]
    two_list = [f"{n}.TWO" for n in base_numbers]
    
    # 合併清單 (yfinance 下載時若代號不存在會自動跳過，不影響執行)
    # 為了掃描效率，我們先抓熱門段位即可，或是全放
    all_potential = tw_list + two_list
    
    # 這裡我們維持原本的名稱，但內容改為全自動生成
    return all_potential

# 因為清單變大(約 17000 檔候選)，我們把 batch_size 調大，並縮短延遲來加快速度
def scan_full_market(all_tickers):
    results_3day = []
    results_6mo = []
    
    # 提高批次量至 100，減少請求次數
    batch_size = 100 
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    status_text = st.empty()
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        status_text.text(f"掃描進度: {i+1}/{len(batches)} 批次 | 正在檢索台股區段: {batch[0]}...")
        
        try:
            # yfinance 的 threads=True 會自動處理無效代號，這非常方便
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=10)
            
            # 只有抓到數據的才進行分析
            valid_tickers = [t for t in batch if t in data and not data[t].empty]
            
            for ticker in valid_tickers:
                df = data[ticker]
                if len(df) < 30: continue
                
                # --- 以下維持你原本運作正常的篩選邏輯 ---
                for lookback in range(7):
                    idx = -(lookback + 1)
                    df_sub = df.iloc[:idx+1]
                    if len(df_sub) < 20: continue
                    
                    vol_in_thousands = float(df_sub['Volume'].iloc[-1]) / 1000
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
            # 縮短延遲，加快全區段掃描
            time.sleep(0.5) 
        except Exception:
            continue
            
    status_text.empty()
    return pd.DataFrame(results_3day), pd.DataFrame(results_6mo)
