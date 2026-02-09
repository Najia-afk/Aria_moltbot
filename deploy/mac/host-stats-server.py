#!/usr/bin/env python3
"""
Aria Host Stats Server
Simple HTTP server exposing Mac system stats on port 8888
Run via launchd for persistent monitoring
"""

import json
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone


def get_memory_stats():
    """Get RAM and swap usage using vm_stat and sysctl"""
    try:
        # Get page size
        page_size = int(subprocess.check_output(['sysctl', '-n', 'hw.pagesize']).decode().strip())
        
        # Get total RAM
        total_bytes = int(subprocess.check_output(['sysctl', '-n', 'hw.memsize']).decode().strip())
        total_gb = total_bytes / (1024**3)
        
        # Parse vm_stat for memory breakdown
        vm_stat = subprocess.check_output(['vm_stat']).decode()
        stats = {}
        for line in vm_stat.split('\n'):
            if ':' in line:
                key, val = line.split(':')
                val = val.strip().rstrip('.')
                try:
                    stats[key.strip()] = int(val)
                except ValueError:
                    pass
        
        # Calculate used memory (active + wired + compressed)
        pages_active = stats.get('Pages active', 0)
        pages_wired = stats.get('Pages wired down', 0)
        pages_compressed = stats.get('Pages occupied by compressor', 0)
        used_pages = pages_active + pages_wired + pages_compressed
        used_gb = (used_pages * page_size) / (1024**3)
        
        percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        
        return {
            "used_gb": round(used_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent": round(percent, 1)
        }
    except Exception as e:
        return {"used_gb": 0, "total_gb": 16, "percent": 0, "error": str(e)}


def get_swap_stats():
    """Get swap usage using sysctl"""
    try:
        swap_info = subprocess.check_output(['sysctl', 'vm.swapusage']).decode()
        # Parse: vm.swapusage: total = 2048.00M  used = 1024.00M  free = 1024.00M
        parts = swap_info.split()
        total_mb = float(parts[3].rstrip('M'))
        used_mb = float(parts[6].rstrip('M'))
        
        total_gb = total_mb / 1024
        used_gb = used_mb / 1024
        percent = (used_gb / total_gb) * 100 if total_gb > 0 else 0
        
        return {
            "used_gb": round(used_gb, 2),
            "total_gb": round(total_gb, 2),
            "percent": round(percent, 1)
        }
    except Exception as e:
        return {"used_gb": 0, "total_gb": 0, "percent": 0, "error": str(e)}


def get_disk_stats():
    """Get root disk usage using df"""
    try:
        df_output = subprocess.check_output(['df', '-g', '/']).decode()
        lines = df_output.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            total_gb = int(parts[1])
            used_gb = int(parts[2])
            percent = int(parts[4].rstrip('%'))
            return {
                "used_gb": used_gb,
                "total_gb": total_gb,
                "percent": percent
            }
    except Exception as e:
        return {"used_gb": 0, "total_gb": 500, "percent": 0, "error": str(e)}
    return {"used_gb": 0, "total_gb": 500, "percent": 0}


def get_smart_status():
    """Get SSD SMART status using diskutil"""
    try:
        # Get SMART status for the main disk
        info = subprocess.check_output(['diskutil', 'info', '/']).decode()
        healthy = 'Verified' in info or 'SMART Status' not in info
        status = "healthy" if healthy else "warning"
        return {"status": status, "healthy": healthy}
    except Exception:
        return {"status": "unknown", "healthy": True}


class StatsHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress default logging
        pass
    
    def do_GET(self):
        if self.path == '/stats' or self.path == '/':
            stats = {
                "ram": get_memory_stats(),
                "swap": get_swap_stats(),
                "disk": get_disk_stats(),
                "smart": get_smart_status(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hostname": subprocess.check_output(['hostname']).decode().strip()
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        else:
            self.send_response(404)
            self.end_headers()


def main():
    port = 8888
    server = HTTPServer(('0.0.0.0', port), StatsHandler)
    print(f"🖥️  Aria Host Stats Server running on port {port}")
    server.serve_forever()


if __name__ == '__main__':
    main()
