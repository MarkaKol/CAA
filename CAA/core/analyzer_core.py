import json
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import ANALYZER_CONFIG, load_triggers_db
from utils.logger import setup_logger

logger = setup_logger(__name__)

class AntiFraudAnalyzer:
    def __init__(self, triggers_db_path: Path = None):
        self.triggers_db_path = triggers_db_path or ANALYZER_CONFIG["triggers_db_path"]
        self.triggers = self._load_triggers()
        self.scores = {}
        
    def _load_triggers(self) -> Dict:
        with open(self.triggers_db_path, "r") as f:
            return json.load(f)
    
    def analyze_report(self, report_path: Path) -> Dict:
        with open(report_path, "r") as f:
            report = json.load(f)
        
        analysis = {
            "scan_id": report.get("scan_id"),
            "url": report.get("url"),
            "profile": report.get("profile"),
            "suspicion_score": 0,
            "detected_triggers": [],
            "trigger_counts": Counter(),
            "network_endpoints": [],
            "canvas_attempts": [],
            "webgl_params": [],
            "behavior_events": [],
            "timing_checks": [],
            "recommendations": [],
            "risk_level": "low"
        }
        
        logs = report.get("logs", [])
        
        for log in logs:
            self._process_log(log, analysis)
        
        analysis["suspicion_score"] = min(analysis["suspicion_score"], 100)
        
        if analysis["suspicion_score"] >= self.triggers["scoring"]["critical_suspicion"]:
            analysis["risk_level"] = "critical"
        elif analysis["suspicion_score"] >= self.triggers["scoring"]["high_suspicion"]:
            analysis["risk_level"] = "high"
        elif analysis["suspicion_score"] >= self.triggers["scoring"]["medium_suspicion"]:
            analysis["risk_level"] = "medium"
            
        self._generate_recommendations(analysis)
        
        return analysis
    
    def _process_log(self, log: Dict, analysis: Dict):
        log_type = log.get("type")
        
        if log_type == "navigator":
            prop = log.get("property")
            for category, data in self.triggers["triggers"].items():
                for check in data["checks"]:
                    if check.get("property") == prop:
                        analysis["detected_triggers"].append(f"{category}:{prop}")
                        analysis["trigger_counts"][category] += 1
                        analysis["suspicion_score"] += data["weight"]
                        
        elif log_type == "canvas":
            analysis["canvas_attempts"].append(log)
            analysis["suspicion_score"] += self.triggers["triggers"]["fingerprint"]["weight"]
            analysis["detected_triggers"].append("canvas:fingerprint")
            
        elif log_type == "webgl":
            analysis["webgl_params"].append(log)
            analysis["suspicion_score"] += self.triggers["triggers"]["fingerprint"]["weight"]
            analysis["detected_triggers"].append("webgl:fingerprint")
            
        elif log_type == "event_listener":
            event_type = log.get("eventType")
            analysis["behavior_events"].append(event_type)
            if event_type in ["mousemove", "keydown", "wheel"]:
                analysis["trigger_counts"]["behavior"] += 1
                
        elif log_type == "network":
            url = log.get("url", "")
            analysis["network_endpoints"].append(url)
            for pattern in self.triggers["triggers"]["network"]["patterns"]:
                if pattern in url:
                    analysis["suspicion_score"] += self.triggers["triggers"]["network"]["weight"]
                    analysis["detected_triggers"].append(f"network:{pattern}")
                    
        elif log_type == "timing":
            analysis["timing_checks"].append(log)
            analysis["suspicion_score"] += self.triggers["triggers"]["timing"]["weight"]
    
    def _generate_recommendations(self, analysis: Dict):
        recommendations = []
        
        if analysis["suspicion_score"] > 50:
            recommendations.append("High fingerprinting activity detected")
            
        if len(analysis["canvas_attempts"]) > 0:
            recommendations.append("Implement canvas randomization")
            
        if len(analysis["webgl_params"]) > 0:
            recommendations.append("Override WebGL getParameter for detected params")
            
        if analysis["trigger_counts"].get("environment", 0) > 3:
            recommendations.append("Spoof environment properties (webdriver, plugins, languages)")
            
        if len(analysis["behavior_events"]) < 2:
            recommendations.append("Add human-like behavior simulation")
            
        if len(analysis["network_endpoints"]) > 0:
            recommendations.append(f"Monitor {len(analysis['network_endpoints'])} network endpoints")
            
        analysis["recommendations"] = recommendations
    
    def compare_reports(self, clean_report_path: Path, spoofed_report_path: Path) -> Dict:
        clean = self.analyze_report(clean_report_path)
        spoofed = self.analyze_report(spoofed_report_path)
        
        diff = {
            "clean_score": clean["suspicion_score"],
            "spoofed_score": spoofed["suspicion_score"],
            "score_difference": spoofed["suspicion_score"] - clean["suspicion_score"],
            "clean_triggers": set(clean["detected_triggers"]),
            "spoofed_triggers": set(spoofed["detected_triggers"]),
            "extra_in_spoofed": list(set(spoofed["detected_triggers"]) - set(clean["detected_triggers"])),
            "missing_in_spoofed": list(set(clean["detected_triggers"]) - set(spoofed["detected_triggers"])),
            "clean_network": clean["network_endpoints"],
            "spoofed_network": spoofed["network_endpoints"]
        }
        
        return diff

def load_triggers_db():
    analyzer = AntiFraudAnalyzer()
    return analyzer.triggers