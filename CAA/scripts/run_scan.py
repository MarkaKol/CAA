#!/usr/bin/env python3
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ['LD_LIBRARY_PATH'] = '/root/CFM/cpp_core/build/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

from core.scanner_main_v2 import CFMScannerV2
from core.analyzer_core import AntiFraudAnalyzer
from core.report_generator import ReportGenerator

async def main():
    url = "https://videoplayer.mediavi.ru/"
    
    print("=" * 60)
    print("CAA - CFM AntiFraud Analyzer")
    print("=" * 60)
    print(f"Target: {url}")
    print()
    
    scanner = CFMScannerV2()
    result = await scanner.scan(url, "clean")
    
    if result["success"]:
        print(f"\n✓ Scan completed!")
        print(f"  Scan ID: {result['scan_id']}")
        print(f"  Logs collected: {len(result['logs'])}")
        print(f"  Blocked: {result['blocked']}")
        
        if result["screenshot_path"]:
            print(f"  Screenshot: {result['screenshot_path']}")
        
        print("\nAnalyzing results...")
        analyzer = AntiFraudAnalyzer()
        
        raw_report_path = Path(__file__).parent / "reports" / "raw" / f"{result['scan_id']}.json"
        analysis = analyzer.analyze_report(raw_report_path)
        
        print("\n" + "=" * 60)
        print("ANALYSIS RESULTS")
        print("=" * 60)
        print(f"  Suspicion score: {analysis['suspicion_score']}/100")
        print(f"  Risk level: {analysis['risk_level'].upper()}")
        print(f"  Detected triggers: {len(analysis['detected_triggers'])}")
        
        if analysis['detected_triggers']:
            print("\n  Top triggers:")
            for trigger in analysis['detected_triggers'][:10]:
                print(f"    - {trigger}")
        
        if analysis['network_endpoints']:
            print("\n  Network endpoints detected:")
            for endpoint in analysis['network_endpoints'][:5]:
                print(f"    - {endpoint}")
        
        if analysis['recommendations']:
            print("\n  RECOMMENDATIONS:")
            for rec in analysis['recommendations']:
                print(f"    ! {rec}")
        
        generator = ReportGenerator()
        html_path = generator.generate_html(analysis)
        print(f"\n  HTML report: {html_path}")
        
    else:
        print(f"\n✗ Scan failed: {result['error']}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())