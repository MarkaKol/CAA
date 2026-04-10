import json
import re
from urllib.parse import urlparse
from collections import Counter
from typing import Dict, List, Set

class NetworkAnalyzer:
    def __init__(self):
        self.endpoints = []
        self.domains = []
        self.request_patterns = []
    
    def extract_endpoints(self, logs: List[Dict]) -> Dict:
        endpoints = []
        domains = set()
        methods = Counter()
        
        for log in logs:
            if log.get("type") == "network":
                url = log.get("url", "")
                if url:
                    endpoints.append(url)
                    try:
                        parsed = urlparse(url)
                        domains.add(parsed.netloc)
                        methods[log.get("method_type", "GET")] += 1
                    except:
                        pass
        
        return {
            "endpoints": endpoints,
            "domains": list(domains),
            "methods": dict(methods),
            "unique_endpoints": list(set(endpoints))
        }
    
    def find_anti_fraud_patterns(self, endpoints: List[str], patterns: List[str]) -> List[str]:
        detected = []
        for endpoint in endpoints:
            for pattern in patterns:
                if re.search(pattern, endpoint, re.IGNORECASE):
                    detected.append(endpoint)
                    break
        return detected
    
    def extract_post_data(self, logs: List[Dict]) -> List[Dict]:
        post_data = []
        for log in logs:
            if log.get("type") == "network" and log.get("method_type") == "POST":
                post_data.append({
                    "url": log.get("url"),
                    "body": log.get("body"),
                    "headers": log.get("headers"),
                    "timestamp": log.get("timestamp")
                })
        return post_data
    
    def get_endpoint_frequency(self, logs: List[Dict]) -> Dict:
        freq = Counter()
        for log in logs:
            if log.get("type") == "network":
                url = log.get("url", "")
                if url:
                    freq[url] += 1
        return dict(freq.most_common(20))
    
    def analyze_network_flow(self, logs: List[Dict]) -> Dict:
        endpoints = self.extract_endpoints(logs)
        flow = []
        
        for log in logs:
            if log.get("type") == "network":
                flow.append({
                    "time": log.get("timestamp"),
                    "url": log.get("url"),
                    "method": log.get("method_type")
                })
        
        return {
            "total_requests": len(flow),
            "unique_endpoints": len(endpoints["unique_endpoints"]),
            "domains": endpoints["domains"],
            "flow_sequence": flow[:50]
        }