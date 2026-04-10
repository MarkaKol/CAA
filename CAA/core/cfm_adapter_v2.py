import builtins
import sys
import os
import json
import time
import random
import threading
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime

sys.path.insert(0, '/root/CFM/cpp_core/build')
sys.path.insert(0, '/root/CFM/cpp_core/build/lib')

os.environ['LD_LIBRARY_PATH'] = '/root/CFM/cpp_core/build/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

try:
    import cfm_core as cfm
except ImportError as e:
    print(f"Failed to import cfm_core: {e}")
    print("Make sure /root/CFM/cpp_core/build/lib is in LD_LIBRARY_PATH")
    raise

from config.settings import CFM_METRIC_PATH, CFM_PROXIES_PATH, CFM_GOST_PATH

class CFMAdapterV2:
    def __init__(self):
        self.bot = None
        self.config = None
        self.bot_id = None
        self.bridge = None
        self._event_handlers = {
            "console": [],
            "network": [],
            "page": []
        }
        self._logs = []
        self._original_print = print
        
    def _import_metric_modules(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("metric", CFM_METRIC_PATH)
        metric = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metric)
        
        self.DeviceProfile = metric.DeviceProfile
        self.create_config_with_local_proxy = metric.create_config_with_local_proxy
        self.proxy_manager = metric.proxy_manager
        
        if not hasattr(self.proxy_manager, 'proxies') or not self.proxy_manager.proxies:
            if hasattr(self.proxy_manager, 'load_proxies'):
                self.proxy_manager.load_proxies()
        
        return True
    
    async def start(self, profile_name: str = "clean"):
        self._import_metric_modules()
        
        self.bot_id = f"caa_{int(time.time())}"
        
        device_profile = self.DeviceProfile.get_random()
        
        proxy_info = self.proxy_manager.get_random_proxy()
        if proxy_info:
            try:
                self.bridge = self.proxy_manager.create_bridge(proxy_info, self.bot_id)
                if self.bridge:
                    local_proxy_url = self.bridge.get_local_proxy_url()
                else:
                    local_proxy_url = None
            except Exception as e:
                print(f"Proxy bridge failed: {e}")
                local_proxy_url = None
        else:
            local_proxy_url = None
        
        self.config = self.create_config_with_local_proxy(device_profile, local_proxy_url, self.bot_id)
        
        js_dir = Path(__file__).parent.parent / "js"
        preload_scripts = []
        for js_file in ["trap_injected.js", "canvas_trap.js", "network_trap.js", "behavior_trap.js"]:
            js_path = js_dir / js_file
            if js_path.exists():
                with open(js_path, "r") as f:
                    preload_scripts.append(f.read())
        
        self.config.preload_scripts = preload_scripts
        self.config.headless = False
        
        self.bot = cfm.BotInstance(self.config)
        
        if not self.bot.start():
            raise Exception("Failed to start CFM")
        
        await asyncio.sleep(3)
        
        try:
            self.bot.set_context_spoofing("https://google.com")
        except:
            pass
        
        try:
            self.bot.apply_full_protection()
        except:
            pass
        
        self._setup_log_capture()
        
        return True
    
    def _setup_log_capture(self):
        def capture_log(*args, **kwargs):
            msg = str(args[0]) if args else ""
            if "[CAA_TRAP]" in msg:
                try:
                    data = json.loads(msg.split("[CAA_TRAP]")[1])
                    self._logs.append(data)
                    for handler in self._event_handlers["console"]:
                        try:
                            handler(data)
                        except:
                            pass
                except:
                    pass
            self._original_print(*args, **kwargs)
        
        import builtins
        builtins.print = capture_log
    
    async def navigate(self, url: str):
        result = self.bot.navigate(url, timeout_ms=30000)
        if not result.success:
            raise Exception(f"Navigation failed: {result.error}")
        return True
    
    async def wait_for_network_idle(self, idle_time: float = 3):
        await asyncio.sleep(idle_time)
    
    async def screenshot(self, path: str):
        try:
            result = self.bot.screenshot(path)
            return result.success if hasattr(result, 'success') else True
        except:
            return False
    
    async def get_page_text(self) -> str:
        js = "document.body ? document.body.innerText : ''"
        try:
            result = self.bot.execute_javascript(js, await_promise=False, return_by_value=True)
            if result and hasattr(result, 'success') and result.success:
                return str(result.value)
        except:
            pass
        return ""
    
    async def execute_js(self, script: str) -> str:
        try:
            result = self.bot.execute_javascript(script, await_promise=False, return_by_value=True)
            if result and hasattr(result, 'success') and result.success:
                return str(result.value)
        except:
            pass
        return ""
    
    def on(self, event: str, handler: Callable):
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)
    
    async def get_logs(self):
        return self._logs.copy()
    
    async def stop(self):
        builtins.print = self._original_print
        
        if self.bot:
            try:
                self.bot.stop()
            except:
                pass
            self.bot = None
        
        if self.bridge and hasattr(self, 'proxy_manager'):
            try:
                self.proxy_manager.stop_bridge(self.bot_id)
            except:
                pass
            self.bridge = None
        
        self._logs = []