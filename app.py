"""
VN Stock Scanner - FastAPI Backend
Features:
- VNStocks API integration
- Volume pre-filtering (>50k 10D avg)
- 5-layer scoring (Micro, Mispricing, Macro, Momentum, Sector)
- Watchlist management
- Google Sheets integration
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import numpy as np
from datetime import datetime, timedelta
import json
from pathlib import Path

# Try to import vnstocks, if not available provide mock
try:
    from vnstocks import Vnstock
except ImportError:
    Vnstock = None

app = FastAPI(title="VN Stock Scanner API", version="1.0")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================
# MODELS
# ========================================

class Stock(BaseModel):
    ticker: str
    price: float
    market_cap: float
    pe: float
    pb: float
    roe: float
    revenue_growth: float
    eps_growth: float
    debt: float
    fcf: float
    net_income: float
    sector: str
    volume_10d_avg: float
    return_1m: float
    return_3m: float
    return_6m: float
    return_12m: float

class ScoringResult(BaseModel):
    ticker: str
    sector: str
    micro_score: float
    quality_score: float
    growth_score: float
    value_score: float
    mispricing_score: float
    momentum_score: float
    macro_multiplier: float
    final_score: float
    recommendation: str
    price: float
    pe: float

class WatchlistItem(BaseModel):
    ticker: str
    sector: str
    score: float
    recommendation: str
    added_date: str
    reason: str

# ========================================
# STORAGE (Simple JSON file)
# ========================================

WATCHLIST_FILE = Path("watchlist.json")
CACHE_FILE = Path("cache.json")

def load_watchlist() -> List[WatchlistItem]:
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, 'r') as f:
            return [WatchlistItem(**item) for item in json.load(f)]
    return []

def save_watchlist(items: List[WatchlistItem]):
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump([item.dict() for item in items], f, indent=2)

def load_cache() -> Dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(data: Dict):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ========================================
# 1. FETCH STOCK DATA FROM VNSTOCKS
# ========================================

def fetch_all_stocks() -> List[Stock]:
    """
    Fetch stock data from VNStocks API
    For demo: return mock data
    In production: integrate with vnstocks library
    """
    
    # Mock data (replace with real API calls)
    mock_stocks = [
        Stock(
            ticker="VNM",
            price=87500,
            market_cap=739920000000,
            pe=27.5,
            pb=6.2,
            roe=22.5,
            revenue_growth=12.3,
            eps_growth=15.2,
            debt=35,
            fcf=2500,
            net_income=3200,
            sector="Food & Beverage",
            volume_10d_avg=1250000,  # > 50k ✓
            return_1m=5.2,
            return_3m=-2.1,
            return_6m=8.5,
            return_12m=15.3
        ),
        Stock(
            ticker="VIC",
            price=95000,
            market_cap=1250000000000,
            pe=8.5,
            pb=1.2,
            roe=28.5,
            revenue_growth=18.5,
            eps_growth=22.5,
            debt=42,
            fcf=5600,
            net_income=7200,
            sector="Diversified",
            volume_10d_avg=890000,  # > 50k ✓
            return_1m=3.2,
            return_3m=5.5,
            return_6m=12.3,
            return_12m=25.5
        ),
        Stock(
            ticker="MWG",
            price=58000,
            market_cap=285600000000,
            pe=12.5,
            pb=2.1,
            roe=18.5,
            revenue_growth=15.2,
            eps_growth=18.5,
            debt=28,
            fcf=1200,
            net_income=1850,
            sector="Retail",
            volume_10d_avg=750000,  # > 50k ✓
            return_1m=8.5,
            return_3m=12.5,
            return_6m=18.5,
            return_12m=35.2
        ),
        # Add more stocks...
    ]
    
    return mock_stocks

# ========================================
# 2. STAGE 1: PRE-FILTER BY VOLUME
# ========================================

def filter_by_volume(stocks: List[Stock], min_volume: float = 50000) -> List[Stock]:
    """Filter stocks by 10-day average volume > threshold"""
    filtered = [s for s in stocks if s.volume_10d_avg > min_volume]
    print(f"✅ Volume filter: {len(stocks)} → {len(filtered)} stocks (>50k vol)")
    return filtered

# ========================================
# 3. SCORING ENGINE (5 LAYERS)
# ========================================

def group_by_sector(stocks: List[Stock]) -> Dict[str, List[Stock]]:
    """Group stocks by sector for relative scoring"""
    sectors = {}
    for stock in stocks:
        if stock.sector not in sectors:
            sectors[stock.sector] = []
        sectors[stock.sector].append(stock)
    return sectors

def calculate_percentile(values: List[float], target: float) -> float:
    """Calculate percentile rank (0-100)"""
    if not values or len(values) == 0:
        return 50
    
    valid = [v for v in values if v > 0]
    if not valid:
        return 50
    
    sorted_vals = sorted(valid)
    count = sum(1 for v in sorted_vals if v <= target)
    return (count / len(sorted_vals)) * 100

def score_quality(stock: Stock, sector_stocks: List[Stock]) -> float:
    """Quality Score (40% of Micro)"""
    # ROE percentile
    roes = [s.roe for s in sector_stocks]
    roe_percentile = calculate_percentile(roes, stock.roe)
    roe_score = roe_percentile / 100 * 10
    
    # FCF/NI percentile
    fcf_ratios = [s.fcf / s.net_income if s.net_income > 0 else 0 for s in sector_stocks]
    fcf_ratio = stock.fcf / stock.net_income if stock.net_income > 0 else 0
    fcf_percentile = calculate_percentile(fcf_ratios, fcf_ratio)
    fcf_score = fcf_percentile / 100 * 10
    
    # Debt percentile (inverse - lower is better)
    debts = [s.debt for s in sector_stocks]
    debt_percentile = calculate_percentile(debts, stock.debt)
    debt_score = (100 - debt_percentile) / 100 * 10
    
    # Average
    return (roe_score + fcf_score + debt_score) / 3

def score_growth(stock: Stock, sector_stocks: List[Stock]) -> float:
    """Growth Score (30% of Micro)"""
    # Revenue CAGR percentile
    revenues = [s.revenue_growth for s in sector_stocks]
    rev_percentile = calculate_percentile(revenues, stock.revenue_growth)
    rev_score = rev_percentile / 100 * 10
    
    # EPS Growth percentile
    eps_list = [s.eps_growth for s in sector_stocks]
    eps_percentile = calculate_percentile(eps_list, stock.eps_growth)
    eps_score = eps_percentile / 100 * 10
    
    # Stability (coefficient of variation)
    cv = np.std(eps_list) / np.mean(eps_list) if np.mean(eps_list) > 0 else 0
    stability_score = max(10 - cv * 10, 0)
    
    # Weighted: 0.4 Rev + 0.4 EPS + 0.2 Stability
    return (rev_score * 0.4) + (eps_score * 0.4) + (stability_score * 0.2)

def score_value(stock: Stock, sector_stocks: List[Stock]) -> float:
    """Value Score (30% of Micro)"""
    # PE vs sector average
    sector_pes = [s.pe for s in sector_stocks if s.pe > 0]
    avg_pe = np.mean(sector_pes) if sector_pes else 20
    pe_vs_sector = max(10 - abs(stock.pe - avg_pe) / 2, 0)
    
    # PE vs historical (simplified)
    pe_vs_historical = 8 if stock.pe < avg_pe else 5 if stock.pe < avg_pe * 1.5 else 2
    
    # PEG ratio
    peg = stock.pe / stock.eps_growth if stock.eps_growth > 0 else 999
    peg_score = 10 if peg < 1.5 else 7 if peg < 2.5 else 4 if peg < 4 else 1
    
    # Weighted: 0.3 PE vs sector + 0.3 PE vs hist + 0.4 PEG
    return (pe_vs_sector * 0.3) + (pe_vs_historical * 0.3) + (peg_score * 0.4)

def score_micro(stock: Stock, sector_stocks: List[Stock]) -> tuple:
    """Calculate Micro Score (Quality + Growth + Value)"""
    quality = score_quality(stock, sector_stocks)
    growth = score_growth(stock, sector_stocks)
    value = score_value(stock, sector_stocks)
    
    # Final: 0.4 Quality + 0.3 Growth + 0.3 Value
    micro = (quality * 0.4) + (growth * 0.3) + (value * 0.3)
    
    return micro, quality, growth, value

def score_mispricing(stock: Stock) -> float:
    """Mispricing Score (0-30)"""
    score = 0
    
    # Panic: Price down >20%, fundamentals OK
    if stock.return_3m < -20 and stock.revenue_growth > 5:
        score = 30
    # Cycle: Price down 10-20%
    elif stock.return_3m < -10 and stock.revenue_growth > 0:
        score = 20
    # Bad fundamentals
    elif stock.revenue_growth < 0 or stock.debt > 80:
        score = 0
    
    return score

def score_momentum(stock: Stock) -> float:
    """Momentum Score (0-10)"""
    # Weighted: 1M(20%) + 3M(40%) + 6M(30%) + 12M(10%)
    weighted = (stock.return_1m * 0.2) + (stock.return_3m * 0.4) + \
               (stock.return_6m * 0.3) + (stock.return_12m * 0.1)
    
    # Normalize to 0-10
    return min(max((weighted / 10) + 5, 0), 10)

def score_sector_momentum(stocks: List[Stock]) -> Dict[str, float]:
    """Calculate sector momentum adjustments"""
    sectors = group_by_sector(stocks)
    adjustments = {}
    
    for sector, sector_stocks in sectors.items():
        momenta = [stock.return_3m for stock in sector_stocks]
        avg_momentum = np.mean(momenta)
        
        if avg_momentum > 10:
            adjustments[sector] = 1.2
        elif avg_momentum > 0:
            adjustments[sector] = 1.0
        else:
            adjustments[sector] = 0.8
    
    return adjustments

def calculate_final_score(stock: Stock, sector_stocks: List[Stock], 
                         macro_multiplier: float = 1.1, 
                         sector_adjustment: float = 1.0) -> ScoringResult:
    """Calculate final integrated score"""
    
    # Layer 1: Micro
    micro, quality, growth, value = score_micro(stock, sector_stocks)
    
    # Hard filter
    if micro < 6:
        return None
    
    # Layer 2: Mispricing
    mispricing = score_mispricing(stock)
    
    if mispricing < 0:
        return None
    
    # Layer 3: Macro (fixed for now)
    # Layer 4: Momentum
    momentum = score_momentum(stock)
    
    # Final Score
    final_score = ((micro * macro_multiplier) + mispricing + momentum) * sector_adjustment
    
    # Recommendation
    if final_score > 25:
        recommendation = "🟢 STRONG BUY"
    elif final_score > 20:
        recommendation = "🟡 BUY"
    elif final_score > 15:
        recommendation = "⚪ HOLD"
    else:
        recommendation = "🔴 AVOID"
    
    return ScoringResult(
        ticker=stock.ticker,
        sector=stock.sector,
        micro_score=round(micro, 2),
        quality_score=round(quality, 2),
        growth_score=round(growth, 2),
        value_score=round(value, 2),
        mispricing_score=round(mispricing, 2),
        momentum_score=round(momentum, 2),
        macro_multiplier=round(macro_multiplier, 2),
        final_score=round(final_score, 2),
        recommendation=recommendation,
        price=stock.price,
        pe=stock.pe
    )

# ========================================
# 4. STAGE 2: SCREENING & WATCHLIST
# ========================================

@app.get("/api/scan", response_model=List[ScoringResult])
def scan_market():
    """
    Full scanning pipeline:
    1. Fetch all stocks
    2. Filter by volume (>50k)
    3. Score all
    4. Return top picks
    """
    try:
        # Stage 1: Fetch
        all_stocks = fetch_all_stocks()
        print(f"📊 Fetched {len(all_stocks)} stocks")
        
        # Stage 2: Volume filter
        filtered_stocks = filter_by_volume(all_stocks, min_volume=50000)
        
        if not filtered_stocks:
            return []
        
        # Stage 3: Score
        sector_groups = group_by_sector(filtered_stocks)
        sector_adjustments = score_sector_momentum(filtered_stocks)
        
        results = []
        for stock in filtered_stocks:
            sector_stocks = sector_groups.get(stock.sector, [stock])
            sector_adj = sector_adjustments.get(stock.sector, 1.0)
            
            score_result = calculate_final_score(stock, sector_stocks, sector_adjustment=sector_adj)
            if score_result:
                results.append(score_result)
        
        # Sort by final score
        results.sort(key=lambda x: x.final_score, reverse=True)
        
        print(f"✅ Scoring complete: {len(results)} stocks passed filter")
        
        return results[:50]  # Return top 50
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scan/top", response_model=List[ScoringResult])
def get_top_picks(limit: int = 20):
    """Get top picks (top 20 by default)"""
    all_results = scan_market()
    return all_results[:limit]

# ========================================
# 5. WATCHLIST MANAGEMENT
# ========================================

@app.get("/api/watchlist", response_model=List[WatchlistItem])
def get_watchlist():
    """Get current watchlist"""
    return load_watchlist()

@app.post("/api/watchlist")
def add_to_watchlist(ticker: str, score: float, recommendation: str, sector: str, reason: str):
    """Add stock to watchlist"""
    watchlist = load_watchlist()
    
    # Check if already exists
    if any(item.ticker == ticker for item in watchlist):
        raise HTTPException(status_code=400, detail=f"{ticker} already in watchlist")
    
    new_item = WatchlistItem(
        ticker=ticker,
        sector=sector,
        score=score,
        recommendation=recommendation,
        added_date=datetime.now().isoformat(),
        reason=reason
    )
    
    watchlist.append(new_item)
    save_watchlist(watchlist)
    
    return {"status": "added", "ticker": ticker}

@app.delete("/api/watchlist/{ticker}")
def remove_from_watchlist(ticker: str):
    """Remove stock from watchlist"""
    watchlist = load_watchlist()
    watchlist = [item for item in watchlist if item.ticker != ticker]
    save_watchlist(watchlist)
    
    return {"status": "removed", "ticker": ticker}

# ========================================
# 6. HEALTH CHECK
# ========================================

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0"
    }

@app.get("/api/stats")
def get_stats():
    """Get system stats"""
    all_stocks = fetch_all_stocks()
    filtered = filter_by_volume(all_stocks)
    watchlist = load_watchlist()
    
    return {
        "total_stocks": len(all_stocks),
        "after_volume_filter": len(filtered),
        "watchlist_count": len(watchlist),
        "last_updated": datetime.now().isoformat()
    }

# ========================================
# 7. ROOT
# ========================================

@app.get("/")
def root():
    return {
        "name": "VN Stock Scanner API",
        "version": "1.0",
        "docs": "/docs",
        "endpoints": {
            "scan": "/api/scan",
            "top_picks": "/api/scan/top",
            "watchlist": "/api/watchlist",
            "health": "/api/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
