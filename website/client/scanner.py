import requests
import json
import uuid
import time
import os
import logging
import asyncio
import socket
import ipaddress
from datetime import datetime
from typing import Dict, List, Any
import http.client
from concurrent.futures import ThreadPoolExecutor
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PortScanner:
    def __init__(self, rate_limit: int = 1000):
        self.rate_limit = rate_limit
        self.semaphore = asyncio.Semaphore(rate_limit)
        self.executor = ThreadPoolExecutor(max_workers=100)
    
    async def scan_port(self, ip: str, port: int, timeout: float = 1.0) -> Dict[str, Any]:
        """Scan a single port asynchronously"""
        async with self.semaphore:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda: sock.connect_ex((ip, port))
                )
                
                if result == 0:
                    return {
                        "ip": ip,
                        "ports": [{
                            "port": port,
                            "proto": "tcp",
                            "status": "open",
                            "reason": "syn-ack",
                            "ttl": 64
                        }]
                    }
                return None
            except Exception as e:
                logger.debug(f"Error scanning {ip}:{port}: {str(e)}")
                return None
            finally:
                sock.close()
    
    async def scan_ports(self, ip: str, ports: List[int]) -> List[Dict[str, Any]]:
        """Scan multiple ports on an IP address"""
        tasks = [self.scan_port(ip, port) for port in ports]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
    
    async def scan_cidr(self, cidr_block: str, ports: List[int]) -> List[Dict[str, Any]]:
        """Scan all IPs in a CIDR block"""
        try:
            network = ipaddress.ip_network(cidr_block)
            all_results = []
            
            # Process IPs in chunks
            chunk_size = 50
            for i in range(0, network.num_addresses, chunk_size):
                chunk = list(network.hosts())[i:i + chunk_size]
                tasks = [self.scan_ports(str(ip), ports) for ip in chunk]
                chunk_results = await asyncio.gather(*tasks)
                all_results.extend([r for sublist in chunk_results for r in sublist])
                await asyncio.sleep(0.1)  # Small delay between chunks
            
            return all_results
        except Exception as e:
            logger.error(f"Error scanning CIDR block {cidr_block}: {str(e)}")
            return []

class ScannerClient:
    def __init__(self, server_url: str, worker_id: str = None, available_ports: str = None):
        self.server_url = server_url.rstrip('/')
        self.worker_id = worker_id or str(uuid.uuid4())
        self.session = requests.Session()
        self.current_job = None
        self.is_running = True
        self.available_ports = available_ports or "80,443"
        self.scanner = None  # Will be initialized with server-provided rate limit

    def register(self):
        """Register with the server"""
        try:
            response = self.session.post(
                f"{self.server_url}/api/register",
                json={
                    "worker_id": self.worker_id,
                    "available_ports": self.available_ports
                }
            )
            response.raise_for_status()
            logger.info(f"Successfully registered as worker {self.worker_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register: {e}")
            return False

    def send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            response = self.session.post(
                f"{self.server_url}/api/heartbeat",
                json={"worker_id": self.worker_id}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def get_job(self) -> Dict[str, Any]:
        """Get a new job from the server"""
        try:
            response = self.session.get(
                f"{self.server_url}/api/job",
                params={"worker_id": self.worker_id}
            )
            response.raise_for_status()
            job = response.json()
            self.current_job = job
            # Initialize scanner with server-provided rate limit
            self.scanner = PortScanner(rate_limit=job.get('scan_rate', 1000))
            return job
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info("No jobs available")
            else:
                logger.error(f"Failed to get job: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            return None

    async def run_scan(self, cidr_block: str, ports: str) -> List[Dict[str, Any]]:
        """Run port scan on the given CIDR block and ports"""
        try:
            port_list = [int(p.strip()) for p in ports.split(',')]
            logger.info(f"Running scan on {cidr_block} for ports {ports}")
            return await self.scanner.scan_cidr(cidr_block, port_list)
        except Exception as e:
            logger.error(f"Error processing scan results: {e}")
            return []

    def submit_results(self, results: List[Dict[str, Any]]):
        """Submit scan results to the server"""
        if not self.current_job:
            logger.error("No current job to submit results for")
            return False
        
        try:
            response = self.session.post(
                f"{self.server_url}/api/results",
                json={
                    "scan_id": self.current_job["scan_id"],
                    "results": results
                }
            )
            response.raise_for_status()
            logger.info(f"Successfully submitted results for job {self.current_job['scan_id']}")
            self.current_job = None
            return True
        except Exception as e:
            logger.error(f"Failed to submit results: {e}")
            return False

    async def run_async(self):
        """Main loop for the scanner"""
        if not self.register():
            return
        
        while self.is_running:
            try:
                self.send_heartbeat()
                
                job = self.get_job()
                if not job:
                    await asyncio.sleep(10)
                    continue
                
                results = await self.run_scan(job["cidr_block"], job["ports"])
                if results:
                    self.submit_results(results)
                
                await asyncio.sleep(1)
                
            except KeyboardInterrupt:
                logger.info("Shutting down scanner...")
                self.is_running = False
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)

    def run(self):
        """Run the scanner"""
        asyncio.run(self.run_async())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Network Scanner Client")
    parser.add_argument("--server", required=True, help="Server URL (e.g., http://your-server:8000)")
    parser.add_argument("--worker-id", help="Worker ID (optional)")
    parser.add_argument("--available-ports", default="80,443", help="Comma-separated list of ports this worker can scan (default: 80,443)")
    
    args = parser.parse_args()
    
    client = ScannerClient(args.server, args.worker_id, args.available_ports)
    client.run() 