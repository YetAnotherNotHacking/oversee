import asyncio
import aiohttp
import uuid
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import ipaddress
import socket
import ssl
import json
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ScannerClient:
    def __init__(self, server_url: str, available_ports: Optional[List[int]] = None, scan_rate: int = 1000):
        self.server_url = server_url
        self.worker_id = str(uuid.uuid4())
        self.available_ports = available_ports
        self.scan_rate = scan_rate
        self.session = None
        self.is_running = False

    async def connect(self):
        """Initialize HTTP session and register with server"""
        self.session = aiohttp.ClientSession()
        await self.register()

    async def register(self):
        """Register this worker with the server"""
        try:
            ports_str = ','.join(map(str, self.available_ports)) if self.available_ports else ''
            async with self.session.post(
                f"{self.server_url}/api/register",
                json={
                    "worker_id": self.worker_id,
                    "available_ports": ports_str,
                    "scan_rate": self.scan_rate
                }
            ) as response:
                if response.status == 200:
                    logger.info("Successfully registered with server")
                else:
                    logger.error(f"Failed to register with server: {await response.text()}")
        except Exception as e:
            logger.error(f"Error registering with server: {str(e)}")

    async def send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            ports_str = ','.join(map(str, self.available_ports)) if self.available_ports else ''
            async with self.session.post(
                f"{self.server_url}/api/heartbeat",
                json={
                    "worker_id": self.worker_id,
                    "available_ports": ports_str,
                    "scan_rate": self.scan_rate
                }
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to send heartbeat: {await response.text()}")
        except Exception as e:
            logger.error(f"Error sending heartbeat: {str(e)}")

    async def scan_port(self, ip: str, port: int) -> Dict[str, Any]:
        """Scan a single port and return results"""
        result = {
            "ip": ip,
            "ports": [{
                "port": port,
                "state": "closed",
                "protocol": None,
                "banner": None,
                "headers": None
            }]
        }

        try:
            # Try TCP connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            if sock.connect_ex((ip, port)) == 0:
                result["ports"][0]["state"] = "open"
                
                # Try to get banner
                try:
                    sock.send(b"GET / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
                    banner = sock.recv(1024)
                    if banner:
                        result["ports"][0]["banner"] = banner.decode('utf-8', errors='ignore')
                        
                        # Try to parse headers if it's HTTP
                        if b"HTTP/" in banner:
                            result["ports"][0]["protocol"] = "http"
                            try:
                                headers = {}
                                for line in banner.split(b'\r\n')[1:]:
                                    if b':' in line:
                                        key, value = line.split(b':', 1)
                                        headers[key.decode().strip()] = value.decode().strip()
                                result["ports"][0]["headers"] = headers
                            except:
                                pass
                except:
                    pass

                # Try SSL/TLS if it's a common HTTPS port
                if port in [443, 8443, 9443]:
                    try:
                        context = ssl.create_default_context()
                        with socket.create_connection((ip, port), timeout=2) as sock:
                            with context.wrap_socket(sock, server_hostname=ip) as ssock:
                                result["ports"][0]["protocol"] = "https"
                    except:
                        pass

        except Exception as e:
            logger.debug(f"Error scanning {ip}:{port}: {str(e)}")
        finally:
            sock.close()

        return result

    async def scan_ip(self, ip: str, ports: List[int]) -> List[Dict[str, Any]]:
        """Scan all specified ports for an IP address"""
        results = []
        for port in ports:
            result = await self.scan_port(ip, port)
            if result["ports"][0]["state"] == "open":
                results.append(result)
            # Respect scan rate
            await asyncio.sleep(1 / self.scan_rate)
        return results

    async def process_job(self, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process a scan job and return results"""
        cidr_block = job["cidr_block"]
        ports = [int(p) for p in job["ports"].split(',')]
        scan_rate = job["scan_rate"]
        
        # Update scan rate if server requests different rate
        if scan_rate != self.scan_rate:
            self.scan_rate = scan_rate
            logger.info(f"Updated scan rate to {scan_rate} ports/second")

        results = []
        network = ipaddress.ip_network(cidr_block)
        
        for ip in network.hosts():
            ip_results = await self.scan_ip(str(ip), ports)
            results.extend(ip_results)
            
        return results

    async def submit_results(self, scan_id: int, results: List[Dict[str, Any]]):
        """Submit scan results to server"""
        try:
            async with self.session.post(
                f"{self.server_url}/api/results",
                json={
                    "scan_id": scan_id,
                    "results": results
                }
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to submit results: {await response.text()}")
        except Exception as e:
            logger.error(f"Error submitting results: {str(e)}")

    async def run(self):
        """Main worker loop"""
        self.is_running = True
        await self.connect()

        while self.is_running:
            try:
                # Get new job
                async with self.session.get(
                    f"{self.server_url}/api/job",
                    params={"worker_id": self.worker_id}
                ) as response:
                    if response.status == 200:
                        job = await response.json()
                        logger.info(f"Received job {job['scan_id']} for {job['cidr_block']}")
                        
                        # Process job
                        results = await self.process_job(job)
                        logger.info(f"Completed job {job['scan_id']} with {len(results)} results")
                        
                        # Submit results
                        await self.submit_results(job["scan_id"], results)
                    elif response.status == 404:
                        logger.info("No jobs available, waiting...")
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"Error getting job: {await response.text()}")
                        await asyncio.sleep(5)

                # Send heartbeat
                await self.send_heartbeat()
                
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the worker"""
        self.is_running = False
        if self.session:
            await self.session.close()

async def main():
    # Get configuration from environment variables
    server_url = os.getenv('SERVER_URL', 'http://localhost:8000')
    available_ports = os.getenv('AVAILABLE_PORTS')
    if available_ports:
        available_ports = [int(p.strip()) for p in available_ports.split(',')]
    scan_rate = int(os.getenv('SCAN_RATE', '1000'))

    # Create and run scanner client
    client = ScannerClient(server_url, available_ports, scan_rate)
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main()) 