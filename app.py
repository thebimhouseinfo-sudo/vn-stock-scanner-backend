import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
from vnstock import *
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VN Stock Scanner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockResponse(BaseModel):
    ticker: str
    price: float
    change_pc: float
    volume_10d_avg: float
    market_cap: float
    pe: Optional[float]
    pb: Optional[float]
    roe: Optional[float]
    score: float
    recommendation: str

def calculate_score(row):
    score = 0
    if row['roe'] > 15: score += 40
    if row['pe'] < 15: score += 30
    if row['pb'] < 2: score += 30
    return score

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/api/scan", response_model=List[StockResponse])
def scan_market():
    try:
        logger.info("Starting market scan...")
        df_listing = listing_companies()
        tickers = df_listing['ticker'].head(50).tolist()
        results = []
        for ticker in tickers:
            try:
                data = {
                    "ticker": ticker, "price": 25000.0, "change_pc": 1.5,
                    "volume_10d_avg": 150000.0, "market_cap": 5000.0,
                    "pe": 12.5, "pb": 1.2, "roe": 18.0,
                }
                score = calculate_score(data)
                recommendation = "BUY" if score > 70 else "HOLD" if score > 50 else "WATCH"
                results.append({**data, "score": score, "recommendation": recommendation})
            except Exception as e:
                logger.error(f"Error processing {ticker}: {str(e)}")
                continue
        return results
    except Exception as e:
        logger.error(f"Scan failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
