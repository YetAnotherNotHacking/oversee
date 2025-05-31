import socket
import requests
import concurrent.futures
import time
from typing import Dict, List, Optional
import json
from urllib.parse import urlparse
import ssl
import OpenSSL.crypto
from bs4 import BeautifulSoup
import re
import ipaddress

def get_common_ports() -> List[int]:
    """Return list of commonly used ports to scan"""
    return [21, 22, 23, 25, 53, 80, 443, 445, 3306, 3389, 8080, 8443]

def check_port(ip: str, port: int, timeout: float = 0.5) -> Optional[Dict]:
    """Check if a port is open and get basic service info"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        if result == 0:
            service = socket.getservbyport(port)
            return {
                "port": port,
                "service": service,
                "state": "open"
            }
    except:
        pass
    finally:
        sock.close()
    return None

def get_ssl_info(ip: str, port: int = 443) -> Optional[Dict]:
    """Get SSL certificate information"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((ip, port), timeout=1) as sock:
            with context.wrap_socket(sock, server_hostname=ip) as ssock:
                cert = ssock.getpeercert(binary_form=True)
                x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_ASN1, cert)
                return {
                    "issuer": dict(x509.get_issuer().get_components()),
                    "subject": dict(x509.get_subject().get_components()),
                    "version": x509.get_version(),
                    "not_before": x509.get_notBefore().decode(),
                    "not_after": x509.get_notAfter().decode()
                }
    except:
        return None

def get_headers_info(url: str) -> Dict:
    """Get HTTP headers and basic server info"""
    try:
        response = requests.get(url, timeout=2, verify=False)
        return {
            "status_code": response.status_code,
            "server": response.headers.get("Server", "Unknown"),
            "headers": dict(response.headers),
            "content_type": response.headers.get("Content-Type", "Unknown"),
            "content_length": response.headers.get("Content-Length", "Unknown")
        }
    except:
        return {
            "status_code": 0,
            "server": "Unknown",
            "headers": {},
            "content_type": "Unknown",
            "content_length": "Unknown"
        }

def get_tech_stack(url: str) -> List[str]:
    """Detect technologies used by the website"""
    try:
        response = requests.get(url, timeout=2, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        techs = []
        
        # Check meta tags
        meta_tags = soup.find_all('meta')
        for tag in meta_tags:
            if tag.get('name') and 'generator' in tag.get('name').lower():
                techs.append(tag.get('content'))
        
        # Check common script patterns
        scripts = soup.find_all('script')
        for script in scripts:
            src = script.get('src', '')
            if 'jquery' in src.lower():
                techs.append('jQuery')
            if 'react' in src.lower():
                techs.append('React')
            if 'angular' in src.lower():
                techs.append('Angular')
            if 'vue' in src.lower():
                techs.append('Vue.js')
        
        # Check for common frameworks
        if soup.find('div', {'class': re.compile('.*react.*', re.I)}):
            techs.append('React')
        if soup.find('div', {'ng-version'}):
            techs.append('Angular')
        if soup.find('div', {'v-'}):
            techs.append('Vue.js')
        
        return list(set(techs))
    except:
        return []

def analyze_host(ip: str, progress_callback=None) -> Dict:
    """Analyze a host and return comprehensive information"""
    results = {
        "ip": ip,
        "timestamp": time.time(),
        "ports": [],
        "ssl_info": None,
        "http_info": None,
        "tech_stack": [],
        "dns_info": {},
        "security_info": {},
        "network_info": {},
        "content_analysis": {}
    }
    
    # DNS Information
    if progress_callback:
        progress_callback("Gathering DNS information...", 10)
    try:
        results["dns_info"] = {
            "hostname": socket.gethostbyaddr(ip)[0],
            "reverse_dns": socket.gethostbyaddr(ip)[0],
            "aliases": socket.gethostbyaddr(ip)[1]
        }
    except:
        results["dns_info"] = {
            "hostname": "Unknown",
            "reverse_dns": "Unknown",
            "aliases": []
        }
    
    # Network Information
    if progress_callback:
        progress_callback("Gathering network information...", 20)
    try:
        results["network_info"] = {
            "is_private": ipaddress.ip_address(ip).is_private,
            "is_global": ipaddress.ip_address(ip).is_global,
            "is_loopback": ipaddress.ip_address(ip).is_loopback,
            "is_multicast": ipaddress.ip_address(ip).is_multicast,
            "is_reserved": ipaddress.ip_address(ip).is_reserved,
            "version": ipaddress.ip_address(ip).version
        }
    except:
        results["network_info"] = {
            "is_private": False,
            "is_global": False,
            "is_loopback": False,
            "is_multicast": False,
            "is_reserved": False,
            "version": 0
        }
    
    # Check if IP has a web server
    url = f"http://{ip}"
    if progress_callback:
        progress_callback("Checking web server...", 30)
    
    http_info = get_headers_info(url)
    results["http_info"] = http_info
    
    if http_info["status_code"] > 0:
        if progress_callback:
            progress_callback("Analyzing web technologies...", 40)
        results["tech_stack"] = get_tech_stack(url)
        
        # Content Analysis
        if progress_callback:
            progress_callback("Analyzing content...", 50)
        try:
            response = requests.get(url, timeout=2, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract meta information
            meta_info = {}
            for meta in soup.find_all('meta'):
                name = meta.get('name', meta.get('property', ''))
                content = meta.get('content', '')
                if name and content:
                    meta_info[name] = content
            
            # Extract title and description
            title = soup.title.string if soup.title else None
            description = meta_info.get('description', '')
            
            # Count elements
            element_counts = {
                'links': len(soup.find_all('a')),
                'images': len(soup.find_all('img')),
                'forms': len(soup.find_all('form')),
                'tables': len(soup.find_all('table')),
                'scripts': len(soup.find_all('script')),
                'styles': len(soup.find_all('style'))
            }
            
            results["content_analysis"] = {
                "title": title,
                "description": description,
                "meta_tags": meta_info,
                "element_counts": element_counts,
                "content_length": len(response.text),
                "content_type": response.headers.get('Content-Type', 'Unknown')
            }
        except Exception as e:
            results["content_analysis"] = {
                "error": str(e)
            }
        
        if "https" in http_info.get("headers", {}).get("Location", ""):
            if progress_callback:
                progress_callback("Checking SSL certificate...", 60)
            results["ssl_info"] = get_ssl_info(ip)
            
            # Security Information
            if progress_callback:
                progress_callback("Gathering security information...", 70)
            try:
                # Check for security headers
                security_headers = {
                    "X-Frame-Options": http_info["headers"].get("X-Frame-Options", "Not Set"),
                    "X-Content-Type-Options": http_info["headers"].get("X-Content-Type-Options", "Not Set"),
                    "X-XSS-Protection": http_info["headers"].get("X-XSS-Protection", "Not Set"),
                    "Content-Security-Policy": http_info["headers"].get("Content-Security-Policy", "Not Set"),
                    "Strict-Transport-Security": http_info["headers"].get("Strict-Transport-Security", "Not Set")
                }
                
                results["security_info"] = {
                    "security_headers": security_headers,
                    "has_ssl": True,
                    "ssl_info": results["ssl_info"]
                }
            except Exception as e:
                results["security_info"] = {
                    "error": str(e)
                }
    
    # Scan common ports
    if progress_callback:
        progress_callback("Scanning common ports...", 80)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_port = {
            executor.submit(check_port, ip, port): port 
            for port in get_common_ports()
        }
        
        for future in concurrent.futures.as_completed(future_to_port):
            result = future.result()
            if result:
                results["ports"].append(result)
    
    if progress_callback:
        progress_callback("Analysis complete!", 100)
    
    return results

if __name__ == "__main__":
    # Test the analyzer
    def progress_callback(message, percent):
        print(f"{message} ({percent}%)")
    
    result = analyze_host("example.com", progress_callback)
    print(json.dumps(result, indent=2)) 