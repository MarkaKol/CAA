#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.scanner_main import CFMScanner
from core.analyzer_core import AntiFraudAnalyzer
from core.report_generator import ReportGenerator
from utils.fingerprint_comparator import FingerprintComparator
from utils.logger import setup_logger

logger = setup_logger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Compare browser profiles")
    parser.add_argument("--url", required=True, help="Target URL")
    parser.add_argument("--clean", default="clean", help="Clean profile name")
    parser.add_argument("--spoofed", default="cfm_default", help="Spoofed profile name")
    parser.add_argument("--output", default="reports/comparison", help="Output directory")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    scanner = CFMScanner()
    analyzer = AntiFraudAnalyzer()
    comparator = FingerprintComparator()
    
    logger.info(f"Scanning with clean profile: {args.clean}")
    clean_result = await scanner.scan(args.url, args.clean)
    
    logger.info(f"Scanning with spoofed profile: {args.spoofed}")
    spoofed_result = await scanner.scan(args.url, args.spoofed)
    
    if not clean_result["success"] or not spoofed_result["success"]:
        logger.error("One or both scans failed")
        sys.exit(1)
    
    from config import RAW_LOGS_DIR
    
    clean_report_path = RAW_LOGS_DIR / f"{clean_result['scan_id']}.json"
    spoofed_report_path = RAW_LOGS_DIR / f"{spoofed_result['scan_id']}.json"
    
    clean_analysis = analyzer.analyze_report(clean_report_path)
    spoofed_analysis = analyzer.analyze_report(spoofed_report_path)
    
    clean_fp = comparator.extract_fingerprint(clean_result["logs"])
    spoofed_fp = comparator.extract_fingerprint(spoofed_result["logs"])
    
    comparison = analyzer.compare_reports(clean_report_path, spoofed_report_path)
    fingerprint_comparison = comparator.compare(clean_fp, spoofed_fp)
    
    final_report = {
        "url": args.url,
        "clean_profile": args.clean,
        "spoofed_profile": args.spoofed,
        "clean_score": clean_analysis["suspicion_score"],
        "spoofed_score": spoofed_analysis["suspicion_score"],
        "score_difference": comparison["score_difference"],
        "fingerprint_similarity": fingerprint_comparison["similarity_score"],
        "extra_triggers_in_spoofed": comparison["extra_in_spoofed"],
        "missing_triggers_in_spoofed": comparison["missing_in_spoofed"],
        "critical_differences": fingerprint_comparison["critical_differences"],
        "recommendations": spoofed_analysis["recommendations"]
    }
    
    import json
    output_file = output_dir / f"comparison_{clean_result['scan_id']}.json"
    with open(output_file, "w") as f:
        json.dump(final_report, f, indent=2)
    
    generator = ReportGenerator()
    
    comparison_html = output_dir / f"comparison_{clean_result['scan_id']}.html"
    with open(comparison_html, "w") as f:
        f.write(generator._build_html({
            "scan_id": f"comparison_{clean_result['scan_id']}",
            "url": args.url,
            "profile": f"{args.clean} vs {args.spoofed}",
            "suspicion_score": final_report["spoofed_score"],
            "risk_level": spoofed_analysis["risk_level"],
            "detected_triggers": comparison["extra_in_spoofed"],
            "trigger_counts": {"clean": clean_analysis["suspicion_score"], "spoofed": spoofed_analysis["suspicion_score"]},
            "network_endpoints": spoofed_analysis["network_endpoints"],
            "canvas_attempts": spoofed_analysis["canvas_attempts"],
            "webgl_params": spoofed_analysis["webgl_params"],
            "recommendations": final_report["recommendations"]
        }))
    
    logger.info(f"\n=== COMPARISON RESULTS ===")
    logger.info(f"Clean profile score: {clean_analysis['suspicion_score']}")
    logger.info(f"Spoofed profile score: {spoofed_analysis['suspicion_score']}")
    logger.info(f"Score difference: {comparison['score_difference']}")
    logger.info(f"Fingerprint similarity: {fingerprint_comparison['similarity_score']:.2%}")
    logger.info(f"Extra triggers in spoofed: {len(comparison['extra_in_spoofed'])}")
    logger.info(f"Missing triggers in spoofed: {len(comparison['missing_in_spoofed'])}")
    logger.info(f"\nReports saved to: {output_file}, {comparison_html}")

if __name__ == "__main__":
    asyncio.run(main())