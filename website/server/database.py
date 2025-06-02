from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
logger.debug(f"Current working directory: {os.getcwd()}")
logger.debug(f"Looking for .env file in: {os.path.abspath('.env')}")
load_dotenv()
database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")
logger.debug(f"Loaded DATABASE_URL from .env: {database_url}")

Base = declarative_base()

class ScanJob(Base):
    __tablename__ = 'scan_jobs'
    
    id = Column(Integer, primary_key=True)
    cidr_block = Column(String, nullable=False)
    ports = Column(String, nullable=False)  # Comma-separated list of ports
    priority = Column(Integer, default=0)  # Higher number = higher priority
    status = Column(String, default='available')  # available, in_progress, completed, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_to = Column(String, nullable=True)  # Worker ID
    completed_at = Column(DateTime, nullable=True)
    results = relationship("ScanResult", back_populates="scan_job")

class ScanResult(Base):
    __tablename__ = 'scan_results'
    
    id = Column(Integer, primary_key=True)
    scan_job_id = Column(Integer, ForeignKey('scan_jobs.id'))
    ip_address = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    protocol = Column(String, nullable=True)
    banner = Column(String, nullable=True)
    headers = Column(JSON, nullable=True)
    scan_metadata = Column(JSON, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    scan_job = relationship("ScanJob", back_populates="results")

class Worker(Base):
    __tablename__ = 'workers'
    
    id = Column(String, primary_key=True)  # UUID
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    current_job_id = Column(Integer, ForeignKey('scan_jobs.id'), nullable=True)

class Database:
    def __init__(self):
        try:
            self.engine = create_engine(database_url)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise

    def get_session(self):
        return self.Session()

    def create_scan_job(self, cidr_block, ports, priority=0):
        session = self.get_session()
        try:
            job = ScanJob(
                cidr_block=cidr_block,
                ports=ports,
                priority=priority
            )
            session.add(job)
            session.commit()
            logger.info(f"Created new scan job: {job.id}")
            return job
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating scan job: {str(e)}")
            raise

    def get_available_job(self):
        session = self.get_session()
        try:
            job = session.query(ScanJob)\
                .filter(ScanJob.status == 'available')\
                .order_by(ScanJob.priority.desc(), ScanJob.created_at.asc())\
                .first()
            return job
        except Exception as e:
            logger.error(f"Error getting available job: {str(e)}")
            raise

    def assign_job_to_worker(self, job_id, worker_id):
        session = self.get_session()
        try:
            job = session.query(ScanJob).get(job_id)
            if job and job.status == 'available':
                job.status = 'in_progress'
                job.assigned_to = worker_id
                session.commit()
                logger.info(f"Job {job_id} assigned to worker {worker_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error assigning job to worker: {str(e)}")
            raise

    def complete_job(self, job_id, results):
        session = self.get_session()
        try:
            job = session.query(ScanJob).get(job_id)
            if job:
                job.status = 'completed'
                job.completed_at = datetime.utcnow()
                
                # Add results
                for result in results:
                    scan_result = ScanResult(
                        scan_job_id=job_id,
                        ip_address=result['ip'],
                        port=result['ports'][0]['port'],
                        protocol=result.get('protocol'),
                        banner=result.get('banner'),
                        headers=result.get('headers'),
                        scan_metadata=result.get('metadata')
                    )
                    session.add(scan_result)
                
                session.commit()
                logger.info(f"Job {job_id} completed with {len(results)} results")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error completing job: {str(e)}")
            raise

    def update_worker_heartbeat(self, worker_id):
        session = self.get_session()
        try:
            worker = session.query(Worker).get(worker_id)
            if not worker:
                worker = Worker(id=worker_id)
                session.add(worker)
            worker.last_heartbeat = datetime.utcnow()
            session.commit()
            logger.debug(f"Updated heartbeat for worker {worker_id}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating worker heartbeat: {str(e)}")
            raise

    def mark_expired_jobs(self, timeout_minutes=30):
        session = self.get_session()
        try:
            expired_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            expired_jobs = session.query(ScanJob)\
                .filter(ScanJob.status == 'in_progress')\
                .filter(ScanJob.created_at < expired_time)\
                .all()
            
            for job in expired_jobs:
                job.status = 'available'
                job.assigned_to = None
            
            session.commit()
            return len(expired_jobs)
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking expired jobs: {str(e)}")
            raise 