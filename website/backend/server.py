from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import sqlite3
import time
from datetime import datetime, timedelta
import json
from typing import Optional, List, Dict
import uvicorn
from pathlib import Path
import plotly.graph_objects as go
import plotly.utils
import pandas as pd
from collections import deque
import asyncio
from contextlib import contextmanager
import aiosqlite
import threading

DB_PATH = "port80responses.db"
MAX_QUERY_HISTORY = 1000
QUERY_HISTORY_WINDOW = 3600

db_pool = []
pool_lock = threading.Lock()
MAX_POOL_SIZE = 10

def get_db_connection():
    with pool_lock:
        if db_pool:
            return db_pool.pop()
        return sqlite3.connect(DB_PATH, check_same_thread=False)

def release_db_connection(conn):
    with pool_lock:
        if len(db_pool) < MAX_POOL_SIZE:
            db_pool.append(conn)
        else:
            conn.close()

@contextmanager
def get_db():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        release_db_connection(conn)

for _ in range(MAX_POOL_SIZE):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    db_pool.append(conn)

app = FastAPI(
    title="Host Response API",
    description="API for managing and querying host response data",
    version="1.0.0"
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

query_history = deque(maxlen=MAX_QUERY_HISTORY)
query_times = deque(maxlen=MAX_QUERY_HISTORY)

def track_query_time(start_time):
    end_time = time.time()
    query_times.append(end_time - start_time)
    query_history.append(end_time)

async def get_db_stats():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT server) as unique_servers,
                AVG(status_code) as avg_status
            FROM hosts
        """)
        result = cursor.fetchone()
        return {
            "total_records": result['total_records'] or 0,
            "unique_servers": result['unique_servers'] or 0,
            "average_status_code": result['avg_status'] or 0
        }

async def get_performance_stats():
    current_time = time.time()
    recent_queries = [t for t in query_history if current_time - t < QUERY_HISTORY_WINDOW]
    
    if not query_times:
        return {
            "queries_per_second": 0,
            "average_response_time": 0,
            "total_queries": 0
        }
    
    return {
        "queries_per_second": len(recent_queries) / (QUERY_HISTORY_WINDOW / 60),
        "average_response_time": sum(query_times) / len(query_times),
        "total_queries": len(query_history)
    }

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    db_stats = await get_db_stats()
    perf_stats = await get_performance_stats()
    
    current_time = time.time()
    time_series = pd.date_range(
        end=datetime.now(),
        periods=60,
        freq='1min'
    )
    
    query_counts = []
    for t in time_series:
        count = sum(1 for q in query_history if current_time - q < (current_time - t.timestamp()))
        query_counts.append(count)
    
    fig = go.Figure(data=go.Scatter(
        x=time_series,
        y=query_counts,
        mode='lines+markers',
        name='Queries per minute'
    ))
    
    fig.update_layout(
        title='Query Rate Over Time',
        xaxis_title='Time',
        yaxis_title='Queries per minute',
        template='plotly_dark'
    )
    
    plot_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "db_stats": db_stats,
            "perf_stats": perf_stats,
            "plot_json": plot_json
        }
    )

@app.get("/api/hosts")
async def get_hosts(
    server: Optional[str] = None,
    status_code: Optional[int] = None,
    content: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get hosts with optional filtering"""
    start_time = time.time()
    
    query = "SELECT * FROM hosts WHERE 1=1"
    params = []
    
    if server:
        query += " AND server = ?"
        params.append(server)
    
    if status_code:
        query += " AND status_code = ?"
        params.append(status_code)
    
    if content:
        query += " AND (body LIKE ? OR title LIKE ?)"
        search_term = f"%{content}%"
        params.extend([search_term, search_term])
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
    
    track_query_time(start_time)
    return {"data": results}

@app.get("/api/hosts/{ip}")
async def get_host(ip: str):
    start_time = time.time()
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hosts WHERE ip = ?", (ip,))
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Host not found")
    
    track_query_time(start_time)
    return dict(result)

@app.get("/api/stats")
async def get_stats():
    db_stats = await get_db_stats()
    perf_stats = await get_performance_stats()
    
    return {
        "database": db_stats,
        "performance": perf_stats
    }

@app.get("/api/docs")
async def get_api_docs():
    return {
        "endpoints": {
            "/api/hosts": {
                "method": "GET",
                "description": "Get all hosts with optional filtering",
                "parameters": {
                    "server": "Filter by server name",
                    "status_code": "Filter by status code",
                    "content": "Filter by content",
                    "limit": "Number of results to return (1-1000)",
                    "offset": "Number of results to skip"
                }
            },
            "/api/hosts/{ip}": {
                "method": "GET",
                "description": "Get specific host by IP address"
            },
            "/api/stats": {
                "method": "GET",
                "description": "Get current database and performance statistics"
            }
        }
    }

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True) 