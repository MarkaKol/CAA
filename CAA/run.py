#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from scripts.run_scan import main as run_scan
from scripts.batch_scan import main as batch_scan
from scripts.compare_profiles import main as compare_profiles

async def main():
    parser = argparse.ArgumentParser(description="CAA - CFM AntiFraud Analyzer")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    scan_parser = subparsers.add_parser("scan", help="Run single scan")
    scan_parser.add_argument("--url", required=True)
    scan_parser.add_argument("--profile", default="clean")
    scan_parser.add_argument("--analyze", action="store_true")
    
    batch_parser = subparsers.add_parser("batch", help="Run batch scan")
    batch_parser.add_argument("--urls", nargs="+")
    batch_parser.add_argument("--urls-file")
    batch_parser.add_argument("--profiles", nargs="+", default=["clean", "cfm_default", "cfm_stealth"])
    
    compare_parser = subparsers.add_parser("compare", help="Compare profiles")
    compare_parser.add_argument("--url", required=True)
    compare_parser.add_argument("--clean", default="clean")
    compare_parser.add_argument("--spoofed", default="cfm_default")
    
    args = parser.parse_args()
    
    if args.command == "scan":
        await run_scan()
    elif args.command == "batch":
        await batch_scan()
    elif args.command == "compare":
        await compare_profiles()
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())