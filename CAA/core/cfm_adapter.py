import asyncio
import subprocess
import json
from typing import Dict, List, Optional, Callable
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import CFM_CONFIG
from utils.logger import setup_logger

logger = setup_logger(__name__)

class CFMAdapter:
    def __init__(self, binary_path: str = None):
        self.binary_path = binary_path or CFM_CONFIG["binary_path"]
        self.process: Optional[asyncio.subprocess.Process] = None
        self._event_handlers = {
            "console": [],
            "network": [],
            "page": []
        }
        self._connected = False
        
    async def start(self, profile_name: str = "default") -> bool:
        logger.info(f"Starting CFM with profile: {profile_name}")
        
        profile_path = Path(__file__).parent.parent / "profiles" / f"{profile_name}.json"
        
        cmd = [
            self.binary_path,
            "--profile", str(profile_path),
            "--headless" if CFM_CONFIG["headless"] else "--no-headless"
        ]
        
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            asyncio.create_task(self._read_output())
            self._connected = True
            logger.info("CFM started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start CFM: {e}")
            return False
    
    async def stop(self):
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self._connected = False
            logger.info("CFM stopped")
    
    async def navigate(self, url: str) -> bool:
        if not self._connected:
            logger.error("CFM not connected")
            return False
            
        command = json.dumps({"cmd": "navigate", "url": url})
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()
        
        logger.info(f"Navigated to {url}")
        return True
    
    async def screenshot(self, path: str) -> bool:
        command = json.dumps({"cmd": "screenshot", "path": path})
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()
        return True
    
    async def get_page_text(self) -> str:
        command = json.dumps({"cmd": "get_page_text"})
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()
        
        response = await asyncio.wait_for(self._read_response(), timeout=5)
        return response.get("text", "")
    
    async def wait_for_network_idle(self, idle_time: float = 3):
        command = json.dumps({"cmd": "wait_for_network_idle", "idle_time": idle_time})
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()
    
    def on(self, event: str, handler: Callable):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)
    
    async def _read_output(self):
        while self.process and self._connected:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                    
                line_str = line.decode().strip()
                
                if line_str.startswith("[CONSOLE]"):
                    console_data = json.loads(line_str[9:])
                    for handler in self._event_handlers["console"]:
                        handler(console_data)
                        
                elif line_str.startswith("[NETWORK]"):
                    network_data = json.loads(line_str[9:])
                    for handler in self._event_handlers["network"]:
                        handler(network_data)
                        
                elif line_str.startswith("[PAGE]"):
                    page_data = json.loads(line_str[5:])
                    for handler in self._event_handlers["page"]:
                        handler(page_data)
                        
            except Exception as e:
                logger.error(f"Error reading CFM output: {e}")
                break
    
    async def _read_response(self) -> Dict:
        line = await self.process.stdout.readline()
        if line:
            return json.loads(line.decode())
        return {}
    
    async def execute_js(self, script: str) -> str:
        command = json.dumps({"cmd": "execute_js", "script": script})
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()
        
        response = await self._read_response()
        return response.get("result", "")
    
    async def inject_script(self, script_path: Path):
        with open(script_path, "r") as f:
            script_content = f.read()
        
        await self.execute_js(script_content)
        logger.info(f"Injected script: {script_path}")