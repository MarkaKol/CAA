import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.cfm_adapter_v2 import CFMAdapterV2
from utils.logger import setup_logger

logger = setup_logger(__name__)

class CFMScannerV2:
    def __init__(self):
        self.cfm = CFMAdapterV2()
        self.scan_logs = []
        self.current_scan_id = None
        
    async def scan(self, url: str, profile_name: str = "clean", save_screenshot: bool = True) -> Dict:
        self.current_scan_id = f"scan_{int(time.time())}"
        logger.info(f"Starting scan {self.current_scan_id} on {url}")
        
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
            
            await self.cfm.navigate(url)
            
            await asyncio.sleep(15)
            
            if save_screenshot:
                screenshot_path = Path(__file__).parent.parent / "reports" / "screenshots" / f"{self.current_scan_id}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await self.cfm.screenshot(str(screenshot_path))
                result["screenshot_path"] = str(screenshot_path)
            
            result["logs"] = await self.cfm.get_logs()
            result["blocked"] = await self._detect_block()
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            result["error"] = str(e)
            
        finally:
            await self.cfm.stop()
            
        raw_report_path = Path(__file__).parent.parent / "reports" / "raw" / f"{self.current_scan_id}.json"
        raw_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_report_path, "w") as f:
            json.dump(result, f, indent=2)
            
        logger.info(f"Scan completed, report saved to {raw_report_path}")
        return result
    
    def _handle_console_log(self, log_entry: Dict):
        self.scan_logs.append(log_entry)
        
    async def _detect_block(self) -> bool:
        page_text = await self.cfm.get_page_text()
        page_text_lower = page_text.lower()
        
        block_indicators = ["captcha", "blocked", "access denied", "403", "forbidden", "access denied", "block"]
        for indicator in block_indicators:
            if indicator in page_text_lower:
                return True
        return False

async def main():
    scanner = CFMScannerV2()
    result = await scanner.scan("https://videoplayer.mediavi.ru/", "clean")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())