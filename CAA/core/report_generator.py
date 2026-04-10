import json
import html
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import ANALYZED_DIR
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportGenerator:
    def __init__(self):
        self.output_dir = ANALYZED_DIR
        
    def generate_json(self, analysis: Dict, output_path: Path = None) -> Path:
        if output_path is None:
            output_path = self.output_dir / f"{analysis['scan_id']}_analysis.json"
        
        with open(output_path, "w") as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"JSON report saved to {output_path}")
        return output_path
    
    def generate_html(self, analysis: Dict, output_path: Path = None) -> Path:
        if output_path is None:
            output_path = self.output_dir / f"{analysis['scan_id']}_report.html"
        
        html_content = self._build_html(analysis)
        
        with open(output_path, "w") as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved to {output_path}")
        return output_path
    
    def _build_html(self, analysis: Dict) -> str:
        risk_color = {
            "low": "#4caf50",
            "medium": "#ff9800",
            "high": "#f44336",
            "critical": "#9c27b0"
        }.get(analysis["risk_level"], "#757575")
        
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>CAA Report - {analysis['scan_id']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        .header {{ border-bottom: 3px solid {risk_color}; padding-bottom: 10px; margin-bottom: 20px; }}
        .score {{ font-size: 48px; font-weight: bold; color: {risk_color}; }}
        .risk-badge {{ display: inline-block; padding: 5px 15px; border-radius: 20px; background: {risk_color}; color: white; }}
        .section {{ margin-bottom: 30px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }}
        .section-title {{ font-size: 20px; font-weight: bold; margin-bottom: 15px; color: #333; }}
        .trigger-list {{ list-style: none; padding: 0; }}
        .trigger-list li {{ background: #f9f9f9; margin: 5px 0; padding: 8px; border-left: 3px solid {risk_color}; }}
        .recommendation {{ background: #e3f2fd; padding: 10px; margin: 5px 0; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>CAA - AntiFraud Analysis Report</h1>
            <p>Scan ID: {analysis['scan_id']}</p>
            <p>URL: {html.escape(analysis.get('url', 'N/A'))}</p>
            <p>Profile: {analysis.get('profile', 'N/A')}</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">Risk Assessment</h2>
            <div class="score">{analysis['suspicion_score']} / 100</div>
            <div class="risk-badge">Risk Level: {analysis['risk_level'].upper()}</div>
        </div>
        
        <div class="section">
            <h2 class="section-title">Detected Triggers ({len(analysis.get('detected_triggers', []))})</h2>
            <ul class="trigger-list">
                {''.join([f"<li>{html.escape(trigger)}</li>" for trigger in analysis.get('detected_triggers', [])])}
            </ul>
        </div>
        
        <div class="section">
            <h2 class="section-title">Trigger Categories</h2>
            <table>
                <tr><th>Category</th><th>Count</th></tr>
                {''.join([f"<tr><td>{category}</td><td>{count}</td></tr>" for category, count in analysis.get('trigger_counts', {}).items()])}
            </table>
        </div>
        
        <div class="section">
            <h2 class="section-title">Network Endpoints</h2>
            <ul>
                {''.join([f"<li>{html.escape(endpoint)}</li>" for endpoint in analysis.get('network_endpoints', [])])}
            </ul>
        </div>
        
        <div class="section">
            <h2 class="section-title">Canvas Fingerprinting Attempts</h2>
            <p>Count: {len(analysis.get('canvas_attempts', []))}</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">WebGL Parameters Accessed</h2>
            <p>Count: {len(analysis.get('webgl_params', []))}</p>
        </div>
        
        <div class="section">
            <h2 class="section-title">Recommendations</h2>
            {''.join([f"<div class='recommendation'>⚠️ {html.escape(rec)}</div>" for rec in analysis.get('recommendations', [])])}
        </div>
    </div>
</body>
</html>
"""
        return html_template
    
    def generate_markdown(self, analysis: Dict, output_path: Path = None) -> Path:
        if output_path is None:
            output_path = self.output_dir / f"{analysis['scan_id']}_report.md"
        
        md_content = f"""# CAA Analysis Report

**Scan ID:** {analysis['scan_id']}
**URL:** {analysis.get('url', 'N/A')}
**Profile:** {analysis.get('profile', 'N/A')}

## Risk Assessment
- **Suspicion Score:** {analysis['suspicion_score']}/100
- **Risk Level:** {analysis['risk_level'].upper()}

## Detected Triggers ({len(analysis.get('detected_triggers', []))})
{chr(10).join([f'- {trigger}' for trigger in analysis.get('detected_triggers', [])])}

## Trigger Categories
{chr(10).join([f'- {category}: {count}' for category, count in analysis.get('trigger_counts', {}).items()])}

## Network Endpoints
{chr(10).join([f'- {endpoint}' for endpoint in analysis.get('network_endpoints', [])])}

## Recommendations
{chr(10).join([f'- {rec}' for rec in analysis.get('recommendations', [])])}
"""
        with open(output_path, "w") as f:
            f.write(md_content)
        
        return output_path
    
    def generate_all(self, analysis: Dict) -> List[Path]:
        paths = []
        
        if "json" in self.output_formats:
            paths.append(self.generate_json(analysis))
        if "html" in self.output_formats:
            paths.append(self.generate_html(analysis))
        if "markdown" in self.output_formats:
            paths.append(self.generate_markdown(analysis))
        
        return paths
    
    @property
    def output_formats(self):
        from config import ANALYZER_CONFIG
        return ANALYZER_CONFIG.get("export_formats", ["json", "html"])