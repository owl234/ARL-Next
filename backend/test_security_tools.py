import sys
import os
import json

# Ensure we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock ARL-Next database checks to ensure we strictly test the tools, not the DB connection
import app.utils
app.utils.not_in_black_ips = lambda x: True

from app.services.portScan import port_scan
from app.services.nuclei_scan import nuclei_scan
from app.services.infoHunter import run_wih

def test_nmap():
    print("[*] Testing Nmap Port Scan...")
    
    # Case 1: Fast scan
    print("\n  => Case 1.1: Basic Scan on scanme.nmap.org (Ports: 22,80)")
    try:
        res1 = port_scan(targets=['scanme.nmap.org'], ports='22,80')
        print("     Result:", json.dumps(res1, indent=2))
    except Exception as e:
        print("     [!] Failed:", e)
    
    # Case 2: Service Detection
    print("\n  => Case 1.2: Service Detection on scanme.nmap.org (Ports: 22)")
    try:
        res2 = port_scan(targets=['scanme.nmap.org'], ports='22', service_detect=True)
        print("     Result:", json.dumps(res2, indent=2))
    except Exception as e:
        print("     [!] Failed:", e)

def test_nuclei():
    print("\n[*] Testing Nuclei Vulnerability Scan...")
    
    print("  => Case 2.1: Basic Template Execution on http://scanme.nmap.org")
    try:
        res = nuclei_scan(targets=['http://scanme.nmap.org'])
        print("     Found vulnerabilities count:", len(res))
        if len(res) > 0:
            print("     Sample:", json.dumps(res[0], indent=2))
        else:
            print("     No vulnerabilities found, which is normal for scanme.nmap.org.")
    except Exception as e:
        print("     [!] Failed:", e)

def test_wih():
    print("\n[*] Testing Web Info Hunter (wih)...")
    
    print("  => Case 3.1: Information gathering on http://example.com")
    try:
        res = run_wih(sites=['http://example.com'])
        print("     Found records count:", len(res))
        if len(res) > 0:
            print("     Sample:", json.dumps(res[0].__dict__, indent=2))
        else:
            print("     No wih info found, which is normal for example.com.")
    except Exception as e:
        print("     [!] Failed:", e)

if __name__ == '__main__':
    print("=== ARL-Next Security Tools End-to-End Test ===")
    test_nmap()
    test_nuclei()
    test_wih()
    print("=== Test Completed ===")
