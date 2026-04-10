#!/usr/bin/env python3
import asyncio
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent))

from core.scanner_main import CFMScanner
from core.analyzer_core import AntiFraudAnalyzer
from core.report_generator import ReportGenerator
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="CAA Batch Scanner")
    parser.add_argument("--urls", nargs="+", help="List of URLs")
    parser.add_argument("--urls-file", help="File with URLs (one per line)")
    parser.add_argument("--profiles", nargs="+", default=["clean", "cfm_default", "cfm_stealth"], help="Profiles to test")
    parser.add_argument("--output-dir", default="reports/batch", help="Output directory")
    
    args = parser.parse_args()
    
    urls = []
    if args.urls:
        urls = args.urls
    elif args.urls_file:
        with open(args.urls_file, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    
    if not urls:
        logger.error("No URLs provided")
        sys.exit(1)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    batch_results = {
        "timestamp": datetime.now().isoformat(),
        "total_urls": len(urls),
        "total_profiles": len(args.profiles),
        "results": []
    }
    
    scanner = CFMScanner()
    analyzer = AntiFraudAnalyzer()
    generator = ReportGenerator()
    
    for url in urls:
        logger.info(f"\n=== Scanning URL: {url} ===")
        url_results = {"url": url, "profile_results": []}
        
        for profile in args.profiles:
            logger.info(f"Testing profile: {profile}")
            
            try:
                scan_result = await scanner.scan(url, profile)
                
                if scan_result["success"]:
                    from config import RAW_LOGS_DIR
                    report_path = RAW_LOGS_DIR / f"{scan_result['scan_id']}.json"
                    analysis = analyzer.analyze_report(report_path)
                    
                    url_results["profile_results"].append({
                        "profile": profile,
                        "success": True,
                        "blocked": scan_result["blocked"],
                        "suspicion_score": analysis["suspicion_score"],
                        "risk_level": analysis["risk_level"],
                        "triggers_count": len(analysis["detected_triggers"]),
                        "network_requests": len(analysis["network_endpoints"])
                    })
                else:
                    url_results["profile_results"].append({
                        "profile": profile,
                        "success": False,
                        "error": scan_result.get("error")
                    })
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scanning {url} with {profile}: {e}")
                url_results["profile_results"].append({
                    "profile": profile,
                    "success": False,
                    "error": str(e)
                })
        
        batch_results["results"].append(url_results)
    
    batch_summary = {
        "best_profile": None,
        "best_score": 100,
        "profile_stats": {}
    }
    
    for profile in args.profiles:
        profile_scores = []
        for url_result in batch_results["results"]:
            for pr in url_result["profile_results"]:
                if pr["profile"] == profile and pr.get("success"):
                    profile_scores.append(pr.get("suspicion_score", 100))
        
        if profile_scores:
            avg_score = sum(profile_scores) / len(profile_scores)
            batch_summary["profile_stats"][profile] = {
                "avg_suspicion": avg_score,
                "min_suspicion": min(profile_scores),
                "max_suspicion": max(profile_scores),
                "tests_passed": len(profile_scores)
            }
            
            if avg_score < batch_summary["best_score"]:
                batch_summary["best_score"] = avg_score
                batch_summary["best_profile"] = profile
    
    batch_results["summary"] = batch_summary
    
    output_file = output_dir / f"batch_{int(datetime.now().timestamp())}.json"
    with open(output_file, "w") as f:
        json.dump(batch_results, f, indent=2)
    
    logger.info(f"\n=== BATCH SCAN COMPLETE ===")
    logger.info(f"Results saved to: {output_file}")
    logger.info(f"Best profile: {batch_summary['best_profile']} (avg score: {batch_summary['best_score']:.1f})")
    
    for profile, stats in batch_summary["profile_stats"].items():
        logger.info(f"  {profile}: avg={stats['avg_suspicion']:.1f}, tests={stats['tests_passed']}")

if __name__ == "__main__":
    asyncio.run(main())