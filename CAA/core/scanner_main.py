import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import CFM_CONFIG, SCANNER_CONFIG, RAW_LOGS_DIR
from core.cfm_adapter import CFMAdapter
from utils.logger import setup_logger

logger = setup_logger(__name__)

class CFMScanner:
    def __init__(self, cfm_adapter: Optional[CFMAdapter] = None):
        self.cfm = cfm_adapter or CFMAdapter()
        self.scan_logs = []
        self.current_scan_id = None
        
    async def scan(self, url: str, profile_name: str = "clean", save_screenshot: bool = True) -> Dict:
        self.current_scan_id = f"scan_{int(time.time())}"
        logger.info(f"Starting scan {self.current_scan_id} on {url} with profile {profile_name}")
        
        result = {
            "scan_id": self.current_scan_id,
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "profile": profile_name,
            "success": False,
            "logs": [],
            "screenshot_path": None,
            "blocked": False,
            "error": None
        }
        
        try:
            await self.cfm.start(profile_name)
            
            self.cfm.on("console", self._handle_console_log)
            self.cfm.on("network", self._handle_network_log)
            
            await self.cfm.navigate(url)
            
            await asyncio.sleep(SCANNER_CONFIG["wait_before_collect"])
            
            await self.cfm.wait_for_network_idle(SCANNER_CONFIG["wait_for_network_idle"])
            
            if save_screenshot and SCANNER_CONFIG["screenshot_on_block"]:
                screenshot_path = RAW_LOGS_DIR / f"{self.current_scan_id}.png"
                await self.cfm.screenshot(str(screenshot_path))
                result["screenshot_path"] = str(screenshot_path)
            
            result["blocked"] = await self._detect_block()
            result["logs"] = self.scan_logs
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            result["error"] = str(e)
            
        finally:
            await self.cfm.stop()
            
        raw_report_path = RAW_LOGS_DIR / f"{self.current_scan_id}.json"
        with open(raw_report_path, "w") as f:
            json.dump(result, f, indent=2)
            
        logger.info(f"Scan completed, report saved to {raw_report_path}")
        return result
    
    def _handle_console_log(self, log_entry: Dict):
        if "[CAA_TRAP]" in log_entry.get("text", ""):
            try:
                trap_data = json.loads(log_entry["text"].split("[CAA_TRAP]")[1])
                self.scan_logs.append(trap_data)
            except:
                pass
                
    def _handle_network_log(self, network_entry: Dict):
        self.scan_logs.append({
            "type": "network",
            "data": network_entry,
            "timestamp": datetime.now().timestamp()
        })
        
    async def _detect_block(self) -> bool:
        block_indicators = ["captcha", "blocked", "access denied", "403", "forbidden"]
        page_text = await self.cfm.get_page_text()
        page_text_lower = page_text.lower()
        
        for indicator in block_indicators:
            if indicator in page_text_lower:
                return True
        return False
    
    async def scan_multiple_profiles(self, url: str, profiles: List[str]) -> List[Dict]:
        results = []
        for profile in profiles:
            logger.info(f"Scanning with profile: {profile}")
            result = await self.scan(url, profile)
            results.append(result)
            await asyncio.sleep(2)
        return results

async def main():
    scanner = CFMScanner()
    result = await scanner.scan("https://videoplayer.mediavi.ru/", "clean")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())