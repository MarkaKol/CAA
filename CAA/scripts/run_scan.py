#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.scanner_main import CFMScanner
from core.analyzer_core import AntiFraudAnalyzer
from core.report_generator import ReportGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="CAA Scanner")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--profile", default="clean", choices=["clean", "cfm_default", "cfm_stealth"], help="Browser profile")
    parser.add_argument("--analyze", action="store_true", help="Run analysis after scan")
    parser.add_argument("--output", default="auto", help="Output report path")
    
    args = parser.parse_args()
    
    logger.info(f"Starting scan on {args.url} with profile {args.profile}")
    
    scanner = CFMScanner()
    result = await scanner.scan(args.url, args.profile)
    
    if result["success"]:
        logger.info(f"Scan completed. Blocked: {result['blocked']}")
        logger.info(f"Logs collected: {len(result['logs'])}")
        
        if args.analyze:
            logger.info("Running analysis...")
            analyzer = AntiFraudAnalyzer()
            
            from config import RAW_LOGS_DIR
            report_path = RAW_LOGS_DIR / f"{result['scan_id']}.json"
            
            analysis = analyzer.analyze_report(report_path)
            
            generator = ReportGenerator()
            
            if args.output == "auto":
                json_path = generator.generate_json(analysis)
                html_path = generator.generate_html(analysis)
                logger.info(f"Reports saved: {json_path}, {html_path}")
            else:
                output_path = Path(args.output)
                if output_path.suffix == ".json":
                    generator.generate_json(analysis, output_path)
                elif output_path.suffix == ".html":
                    generator.generate_html(analysis, output_path)
                else:
                    generator.generate_json(analysis, output_path.with_suffix(".json"))
                    generator.generate_html(analysis, output_path.with_suffix(".html"))
            
            logger.info(f"Suspicion score: {analysis['suspicion_score']}/100")
            logger.info(f"Risk level: {analysis['risk_level']}")
            
            for rec in analysis["recommendations"][:5]:
                logger.info(f"Recommendation: {rec}")
    else:
        logger.error(f"Scan failed: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())