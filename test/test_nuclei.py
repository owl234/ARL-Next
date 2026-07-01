import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

from app.services.nuclei_scan import NucleiScan, nuclei_scan

logging.basicConfig(level=logging.INFO)

def main():
    targets = ["http://example.com"]
    print(f"Testing NucleiScan with targets: {targets}")
    
    scanner = NucleiScan(targets=targets)
    has_nuclei = scanner.check_have_nuclei()
    print(f"check_have_nuclei() returned: {has_nuclei}")
    
    print("\nExecuting nuclei_scan()...")
    results = nuclei_scan(targets)
    print(f"Results: {results}")

if __name__ == "__main__":
    main()
