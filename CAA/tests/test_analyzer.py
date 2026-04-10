import unittest
import json
import tempfile
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from core.analyzer_core import AntiFraudAnalyzer
from core.report_generator import ReportGenerator
from utils.fingerprint_comparator import FingerprintComparator
from utils.network_utils import NetworkAnalyzer

class TestAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = AntiFraudAnalyzer()
        self.comparator = FingerprintComparator()
        self.network_analyzer = NetworkAnalyzer()
        self.generator = ReportGenerator()
        
        self.sample_logs = [
            {"type": "navigator", "property": "webdriver", "value": False, "timestamp": 1234567890},
            {"type": "navigator", "property": "languages", "value": ["en-US", "en"], "timestamp": 1234567891},
            {"type": "canvas", "method": "toDataURL", "size": {"width": 300, "height": 150}, "timestamp": 1234567892},
            {"type": "webgl", "method": "getParameter", "param": 37445, "value": "Intel Inc.", "timestamp": 1234567893},
            {"type": "network", "url": "https://api.example.com/collect", "method_type": "POST", "timestamp": 1234567894},
            {"type": "behavior", "subtype": "mousemove", "position": {"x": 100, "y": 200}, "timestamp": 1234567895}
        ]
    
    def test_analyze_report(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report = {
                "scan_id": "test_001",
                "url": "https://test.com",
                "profile": "clean",
                "logs": self.sample_logs
            }
            json.dump(report, f)
            f.close()
            
            result = self.analyzer.analyze_report(Path(f.name))
            
            self.assertIn("suspicion_score", result)
            self.assertIn("detected_triggers", result)
            self.assertIn("recommendations", result)
            self.assertGreater(result["suspicion_score"], 0)
            
            Path(f.name).unlink()
    
    def test_trigger_detection(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report = {
                "scan_id": "test_002",
                "url": "https://test.com",
                "profile": "clean",
                "logs": self.sample_logs
            }
            json.dump(report, f)
            f.close()
            
            result = self.analyzer.analyze_report(Path(f.name))
            
            self.assertGreater(len(result["detected_triggers"]), 0)
            self.assertGreater(len(result["network_endpoints"]), 0)
            self.assertGreater(len(result["canvas_attempts"]), 0)
            
            Path(f.name).unlink()
    
    def test_fingerprint_extraction(self):
        fingerprint = self.comparator.extract_fingerprint(self.sample_logs)
        
        self.assertIn("navigator.webdriver", fingerprint)
        self.assertIn("navigator.languages", fingerprint)
        self.assertTrue(fingerprint.get("canvas_fingerprinted", False))
        self.assertTrue(fingerprint.get("webgl_fingerprinted", False))
    
    def test_fingerprint_comparison(self):
        fp1 = {"webdriver": False, "languages": ["en-US"], "resolution": "1920x1080"}
        fp2 = {"webdriver": False, "languages": ["ru-RU"], "resolution": "1920x1080"}
        
        result = self.comparator.compare(fp1, fp2)
        
        self.assertIn("similarity_score", result)
        self.assertIn("differences", result)
        self.assertGreater(result["similarity_score"], 0)
    
    def test_network_analysis(self):
        result = self.network_analyzer.extract_endpoints(self.sample_logs)
        
        self.assertIn("endpoints", result)
        self.assertIn("domains", result)
        self.assertEqual(len(result["endpoints"]), 1)
    
    def test_report_generation(self):
        analysis = {
            "scan_id": "test_003",
            "url": "https://test.com",
            "profile": "clean",
            "suspicion_score": 45,
            "risk_level": "medium",
            "detected_triggers": ["webdriver", "canvas"],
            "trigger_counts": {"fingerprint": 2, "environment": 1},
            "network_endpoints": ["https://api.test.com/collect"],
            "canvas_attempts": [{"size": {"width": 300, "height": 150}}],
            "webgl_params": [{"param": 37445}],
            "recommendations": ["Fix webdriver"]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.json"
            result = self.generator.generate_json(analysis, output_path)
            
            self.assertTrue(result.exists())
            self.assertEqual(result.suffix, ".json")
    
    def test_empty_logs(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report = {
                "scan_id": "test_004",
                "url": "https://test.com",
                "profile": "clean",
                "logs": []
            }
            json.dump(report, f)
            f.close()
            
            result = self.analyzer.analyze_report(Path(f.name))
            
            self.assertEqual(result["suspicion_score"], 0)
            self.assertEqual(len(result["detected_triggers"]), 0)
            
            Path(f.name).unlink()
    
    def test_high_suspicion_score(self):
        high_risk_logs = []
        for i in range(20):
            high_risk_logs.append({"type": "canvas", "timestamp": 1234567890 + i})
            high_risk_logs.append({"type": "webgl", "timestamp": 1234567890 + i})
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report = {
                "scan_id": "test_005",
                "url": "https://test.com",
                "profile": "clean",
                "logs": high_risk_logs
            }
            json.dump(report, f)
            f.close()
            
            result = self.analyzer.analyze_report(Path(f.name))
            
            self.assertGreater(result["suspicion_score"], 70)
            self.assertIn("high", result["risk_level"])
            
            Path(f.name).unlink()

if __name__ == "__main__":
    unittest.main()