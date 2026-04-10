import json
from typing import Dict, List, Any
from collections import Counter

class FingerprintComparator:
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
    
    def compare(self, clean_fp: Dict, spoofed_fp: Dict) -> Dict:
        similarity_score = self._calculate_similarity(clean_fp, spoofed_fp)
        
        differences = self._find_differences(clean_fp, spoofed_fp)
        
        return {
            "similarity_score": similarity_score,
            "is_similar": similarity_score >= self.threshold,
            "differences": differences,
            "critical_differences": self._filter_critical(differences)
        }
    
    def _calculate_similarity(self, fp1: Dict, fp2: Dict) -> float:
        if not fp1 or not fp2:
            return 0.0
        
        all_keys = set(fp1.keys()) | set(fp2.keys())
        if not all_keys:
            return 1.0
        
        matches = 0
        for key in all_keys:
            if key in fp1 and key in fp2:
                if self._values_equal(fp1[key], fp2[key]):
                    matches += 1
        
        return matches / len(all_keys)
    
    def _values_equal(self, val1: Any, val2: Any) -> bool:
        if type(val1) != type(val2):
            return False
        if isinstance(val1, dict):
            return self._calculate_similarity(val1, val2) > 0.9
        if isinstance(val1, list):
            return set(val1) == set(val2)
        return val1 == val2
    
    def _find_differences(self, fp1: Dict, fp2: Dict) -> List[Dict]:
        differences = []
        all_keys = set(fp1.keys()) | set(fp2.keys())
        
        for key in all_keys:
            if key not in fp1:
                differences.append({"key": key, "status": "missing_in_clean", "spoofed_value": fp2.get(key)})
            elif key not in fp2:
                differences.append({"key": key, "status": "missing_in_spoofed", "clean_value": fp1.get(key)})
            elif not self._values_equal(fp1[key], fp2[key]):
                differences.append({
                    "key": key,
                    "status": "different",
                    "clean_value": fp1[key],
                    "spoofed_value": fp2[key]
                })
        
        return differences
    
    def _filter_critical(self, differences: List[Dict]) -> List[Dict]:
        critical_keys = [
            "webdriver", "automation", "plugins", "languages",
            "hardwareConcurrency", "deviceMemory", "userAgent"
        ]
        
        return [d for d in differences if any(key in d.get("key", "") for key in critical_keys)]
    
    def extract_fingerprint(self, logs: List[Dict]) -> Dict:
        fingerprint = {}
        
        for log in logs:
            if log.get("type") == "navigator":
                prop = log.get("property")
                value = log.get("value")
                if prop and value:
                    fingerprint[f"navigator.{prop}"] = value
            
            elif log.get("type") == "screen":
                prop = log.get("property")
                value = log.get("value")
                if prop and value:
                    fingerprint[f"screen.{prop}"] = value
            
            elif log.get("type") == "canvas":
                fingerprint["canvas_fingerprinted"] = True
                fingerprint["canvas_size"] = log.get("size")
            
            elif log.get("type") == "webgl":
                fingerprint["webgl_fingerprinted"] = True
                param_key = f"webgl.param_{log.get('param')}"
                fingerprint[param_key] = log.get("value")
        
        return fingerprint