from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import asyncio
from datetime import datetime, timedelta
import ipaddress
import database
from database import Database, ScanJob, ScanResult, Worker
import os
from dotenv import load_dotenv
import logging
import math

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=os.getenv('LOG_FILE', 'server.log')
)
logger = logging.getLogger(__name__)

app = FastAPI(debug=os.getenv('DEBUG', 'False').lower() == 'true')
db = Database()

# Set up templates
templates = Jinja2Templates(directory="templates")

# Priority order for ports
DEFAULT_PORTS = os.getenv('DEFAULT_PORTS', '80,443,22,21,25,110,143,3306,5432,27017').split(',')
PORT_PRIORITIES = {
    int(port): 100 - (i * 10) for i, port in enumerate(DEFAULT_PORTS)
}

# Constants for job creation
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '256'))  # Number of IPs per chunk
PRIORITY_PORTS = [80, 443, 22, 21]  # High priority ports to scan first

class WorkerRegistration(BaseModel):
    worker_id: str
    available_ports: str
    scan_rate: int = 1000  # Default scan rate per second

class ScanResult(BaseModel):
    scan_id: int
    results: List[Dict[str, Any]]

class JobResponse(BaseModel):
    scan_id: int
    cidr_block: str
    ports: str
    scan_rate: int  # Server will tell client how fast to scan

# API Endpoints
@app.post("/api/register")
async def register_worker(worker: WorkerRegistration):
    """Register a worker and update its heartbeat"""
    logger.info(f"Worker {worker.worker_id} registered with ports {worker.available_ports}")
    db.update_worker_heartbeat(worker.worker_id, worker.available_ports)
    return {"status": "registered"}

@app.post("/api/heartbeat")
async def heartbeat(worker: WorkerRegistration):
    """Update worker heartbeat"""
    db.update_worker_heartbeat(worker.worker_id)
    return {"status": "alive"}

def get_next_unscanned_chunk(session):
    """Find the next chunk of IPs that hasn't been scanned"""
    # Get the latest scanned IP
    latest_result = session.query(database.ScanResult)\
        .order_by(database.ScanResult.ip_address.desc())\
        .first()
    
    if latest_result:
        # Start from the next IP after the last scanned one
        start_ip = ipaddress.IPv4Address(latest_result.ip_address) + 1
    else:
        # Start from the beginning if no results exist
        start_ip = ipaddress.IPv4Address('0.0.0.0')
    
    # Create a chunk starting from this IP
    chunk_end = min(start_ip + CHUNK_SIZE - 1, ipaddress.IPv4Address('255.255.255.255'))
    chunk_network = ipaddress.ip_network(f"{start_ip}/{32 - int(math.log2(CHUNK_SIZE))}", strict=False)
    
    return str(chunk_network)

@app.get("/api/job", response_model=JobResponse)
async def get_job(worker_id: str):
    """Get a new scan job for the worker"""
    db.update_worker_heartbeat(worker_id)
    session = db.get_session()
    
    # Get worker's available ports and scan rate
    worker = session.query(database.Worker).filter(database.Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    available_ports = set(worker.available_ports.split(','))
    scan_rate = worker.scan_rate or 1000  # Default to 1000 if not set
    
    # First try to get an existing available job that matches worker's ports
    job = db.get_available_job(available_ports)
    
    if not job:
        # If no jobs available, create a new one for an unscanned chunk
        try:
            chunk = get_next_unscanned_chunk(session)
            
            # Create high-priority job for this chunk using only available ports
            priority_ports = [p for p in PRIORITY_PORTS if str(p) in available_ports]
            if not priority_ports:
                raise HTTPException(status_code=404, detail="No compatible jobs available")
            
            job = database.ScanJob(
                cidr_block=chunk,
                ports=','.join(map(str, priority_ports)),
                priority=1000  # Highest priority for initial scans
            )
            session.add(job)
            session.commit()
            logger.info(f"Created new job for unscanned chunk: {chunk}")
        except Exception as e:
            logger.error(f"Error creating new job: {str(e)}")
            session.rollback()
            raise HTTPException(status_code=500, detail="Failed to create new job")
    
    if not db.assign_job_to_worker(job.id, worker_id):
        raise HTTPException(status_code=409, detail="Job already assigned")
    
    return {
        "scan_id": job.id,
        "cidr_block": job.cidr_block,
        "ports": job.ports,
        "scan_rate": scan_rate  # Tell client how fast to scan
    }

@app.post("/api/results")
async def submit_results(results: ScanResult):
    """Submit scan results"""
    if not db.complete_job(results.scan_id, results.results):
        raise HTTPException(status_code=404, detail="Job not found")
    
    # After completing a job, check if we should create a full scan job
    session = db.get_session()
    job = session.query(database.ScanJob).get(results.scan_id)
    
    if job and job.ports == ','.join(map(str, PRIORITY_PORTS)):
        # If this was a high-priority scan, create a full scan job
        try:
            full_scan_job = database.ScanJob(
                cidr_block=job.cidr_block,
                ports=os.getenv('DEFAULT_PORTS', '80,443,22,21,25,110,143,3306,5432,27017'),
                priority=500  # Lower priority than initial scan
            )
            session.add(full_scan_job)
            session.commit()
            logger.info(f"Created full scan job for {job.cidr_block}")
        except Exception as e:
            logger.error(f"Error creating full scan job: {str(e)}")
            session.rollback()
    
    return {"status": "success"}

@app.post("/api/create_job")
async def create_job(cidr_block: str, ports: str):
    """Create a new scan job (admin endpoint)"""
    try:
        ipaddress.ip_network(cidr_block)
        port_list = [int(p.strip()) for p in ports.split(',')]
        priority = sum(PORT_PRIORITIES.get(port, 0) for port in port_list)
        job = db.create_scan_job(cidr_block, ports, priority)
        logger.info(f"New job created: {job.id} for {cidr_block}")
        return {"scan_id": job.id, "status": "created"}
    except ValueError as e:
        logger.error(f"Error creating job: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# Dashboard Routes
@app.get("/")
async def dashboard(request: Request):
    """Main dashboard view"""
    session = db.get_session()
    
    # Get statistics
    total_jobs = session.query(database.ScanJob).count()
    completed_jobs = session.query(database.ScanJob).filter(database.ScanJob.status == 'completed').count()
    active_workers = session.query(database.Worker).filter(
        database.Worker.last_heartbeat > datetime.utcnow() - timedelta(minutes=5)
    ).count()
    total_results = session.query(database.ScanResult).count()
    
    # Get recent jobs
    recent_jobs = session.query(database.ScanJob)\
        .order_by(database.ScanJob.created_at.desc())\
        .limit(5)\
        .all()
    
    # Get active workers
    workers = session.query(database.Worker)\
        .filter(database.Worker.last_heartbeat > datetime.utcnow() - timedelta(minutes=5))\
        .all()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "active_page": "dashboard",
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "active_workers": active_workers,
            "total_results": total_results,
            "recent_jobs": recent_jobs,
            "workers": workers
        }
    )

@app.get("/jobs")
async def jobs(request: Request, page: int = 1, per_page: int = 50):
    """Jobs view with pagination"""
    session = db.get_session()
    
    # Calculate total pages
    total_jobs = session.query(database.ScanJob).count()
    total_pages = (total_jobs + per_page - 1) // per_page
    
    # Get paginated jobs
    jobs = session.query(database.ScanJob)\
        .order_by(database.ScanJob.created_at.desc())\
        .offset((page - 1) * per_page)\
        .limit(per_page)\
        .all()
    
    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "active_page": "jobs",
            "jobs": jobs,
            "current_page": page,
            "total_pages": total_pages,
            "per_page": per_page
        }
    )

@app.get("/workers")
async def workers(request: Request):
    """Workers view"""
    session = db.get_session()
    workers = session.query(database.Worker).all()
    
    return templates.TemplateResponse(
        "workers.html",
        {
            "request": request,
            "active_page": "workers",
            "workers": workers,
            "timedelta": timedelta,
            "now": datetime.utcnow()
        }
    )

@app.get("/results")
async def results(request: Request):
    """Results view"""
    session = db.get_session()
    results = session.query(database.ScanResult).order_by(database.ScanResult.discovered_at.desc()).all()
    
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "active_page": "results",
            "results": results
        }
    )

@app.get("/create-job")
async def create_job_form(request: Request):
    """Create job form"""
    return templates.TemplateResponse(
        "create_job.html",
        {
            "request": request,
            "active_page": "create_job"
        }
    )

@app.post("/create-job")
async def create_job_submit(request: Request, cidr_block: str = Form(...), ports: str = Form(...)):
    """Handle job creation form submission"""
    try:
        ipaddress.ip_network(cidr_block)
        port_list = [int(p.strip()) for p in ports.split(',')]
        priority = sum(PORT_PRIORITIES.get(port, 0) for port in port_list)
        job = db.create_scan_job(cidr_block, ports, priority)
        return RedirectResponse(url="/jobs", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse(
            "create_job.html",
            {
                "request": request,
                "active_page": "create_job",
                "error": str(e)
            }
        )

async def cleanup_expired_jobs():
    """Background task to clean up expired jobs"""
    while True:
        try:
            timeout = int(os.getenv('WORKER_TIMEOUT_MINUTES', '30'))
            expired_count = db.mark_expired_jobs(timeout_minutes=timeout)
            if expired_count > 0:
                logger.info(f"Marked {expired_count} jobs as expired")
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
        
        interval = int(os.getenv('WORKER_HEARTBEAT_INTERVAL', '300'))
        await asyncio.sleep(interval)

@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup"""
    logger.info("Starting server...")
    asyncio.create_task(cleanup_expired_jobs())

if __name__ == "__main__":
    import uvicorn
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host=host, port=port)
