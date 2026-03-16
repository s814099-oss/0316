def scan_full_market(all_tickers):
    results = []
    # 每批次 50 檔，這是在速度與被封鎖風險間的最佳平衡點
    batch_size = 50
    batches = [all_tickers[i:i + batch_size] for i in range(0, len(all_tickers), batch_size)]
    
    progress = st.progress(0)
    
    for i, batch in enumerate(batches):
        progress.progress((i + 1) / len(batches))
        try:
            # 批次下載，顯著加速
            data = yf.download(batch, period="1mo", interval="1d", group_by='ticker', threads=True, progress=False)
            
            for ticker in batch:
                # 處理多檔下載後的索引結構
                df = data[ticker] if len(batch) > 1 else data
                if df.empty or len(df) < 20: continue
                
                # 指標計算
                vol_ratio = df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]
                if vol_ratio > 1.5:
                    results.append({"代號": ticker.replace(".TW", ""), "量比": round(float(vol_ratio), 2)})
            
            # 每批次後強制冷卻，避免觸發 429 Error
            time.sleep(random.uniform(5, 8))
            
        except Exception:
            continue
            
    return pd.DataFrame(results)
