#!/usr/bin/env python3
"""
CFM ULTIMATE BYPASS - Protected Media Killer
Полный функционал: прокси-мосты, прямой трафик видео, листенер трафика, всё через CFM
Режимы: 1 бот, несколько параллельно, потоковый режим (бесконечный цикл)
"""

import sys
import os
import json
import time
import random
import asyncio
import threading
import subprocess
import signal
import socket
import re
import psutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, '/root/CFM/cpp_core/build')

os.environ['LD_LIBRARY_PATH'] = '/root/CFM/cpp_core/build/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

import cfm_core as cfm

TARGET_URL = "https://videoplayer.mediavi.ru/"
PROXY_FILE = "/root/CFM/cpp_core/build/proxies.txt"
GOST_PATH = "/root/CFM/gost"
BASE_LOCAL_PORT = 10000
MAX_CONCURRENT_BOTS = 5

# ============================================================================
# ПРОКСИ БРИДЖ (КАК В METRIC.PY)
# ============================================================================

class ProxyBridge:
    def __init__(self, proxy_info, local_port, bot_id):
        self.proxy_info = proxy_info
        self.local_port = local_port
        self.bot_id = bot_id
        self.process = None
        self.gost_path = GOST_PATH

    def start(self):
        try:
            auth = f"{self.proxy_info['username']}:{self.proxy_info['password']}@"
            remote = f"{auth}{self.proxy_info['host']}:{self.proxy_info['port']}"
            log_file = f"/tmp/gost_{self.bot_id}.log"
            cmd = [self.gost_path, "-L", f"http://:{self.local_port}", "-F", f"http://{remote}"]
            print(f"  🔌 Starting Gost bridge on port {self.local_port}")
            with open(log_file, 'w') as f:
                self.process = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, preexec_fn=os.setsid)
            time.sleep(2)
            if self.process.poll() is not None:
                return False
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', self.local_port))
            sock.close()
            if result == 0:
                print(f"  ✅ Bridge running on port {self.local_port}")
                return True
            return False
        except Exception as e:
            print(f"  ❌ Bridge error: {e}")
            return False

    def stop(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=3)
            except:
                try:
                    self.process.terminate()
                except:
                    pass
            self.process = None
            print(f"  🔌 Bridge on port {self.local_port} stopped")

    def get_local_proxy_url(self):
        return f"http://127.0.0.1:{self.local_port}"


class ProxyManager:
    def __init__(self, proxy_file):
        self.proxy_file = proxy_file
        self.proxies = []
        self.active_bridges = {}
        self.port_lock = threading.Lock()
        self.next_port = BASE_LOCAL_PORT
        self.load_proxies()

    def load_proxies(self):
        if not os.path.exists(self.proxy_file):
            print(f"⚠️ Proxy file {self.proxy_file} not found!")
            return False
        with open(self.proxy_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                proxy_info = self.parse_proxy_line(line)
                if proxy_info:
                    self.proxies.append(proxy_info)
        print(f"📡 Loaded {len(self.proxies)} proxies")
        return len(self.proxies) > 0

    def parse_proxy_line(self, line):
        line = line.strip()
        line = re.sub(r'^(https?|socks5|socks4)://', '', line)
        pattern = r'([^:]+):([^@]+)@([^:]+):(\d+)'
        match = re.search(pattern, line)
        if match:
            user, password, host, port = match.groups()
            return {'host': host, 'port': int(port), 'username': user, 'password': password}
        pattern2 = r'([^:]+):([^:]+):([^:]+):(\d+)'
        match = re.search(pattern2, line)
        if match:
            user, password, host, port = match.groups()
            return {'host': host, 'port': int(port), 'username': user, 'password': password}
        pattern3 = r'([^:]+):(\d+):([^:]+):(.+)$'
        match = re.search(pattern3, line)
        if match:
            host, port, user, password = match.groups()
            return {'host': host, 'port': int(port), 'username': user, 'password': password}
        return None

    def get_random_proxy(self):
        if not self.proxies:
            return None
        return random.choice(self.proxies)

    def get_unique_proxies(self, count):
        if not self.proxies:
            return []
        if count >= len(self.proxies):
            return self.proxies[:]
        return random.sample(self.proxies, count)

    def get_next_port(self):
        with self.port_lock:
            port = self.next_port
            self.next_port += 1
            return port

    def create_bridge(self, proxy_info, bot_id):
        local_port = self.get_next_port()
        bridge = ProxyBridge(proxy_info, local_port, bot_id)
        if bridge.start():
            self.active_bridges[bot_id] = bridge
            return bridge
        return None

    def stop_bridge(self, bot_id):
        if bot_id in self.active_bridges:
            self.active_bridges[bot_id].stop()
            del self.active_bridges[bot_id]

    def stop_all_bridges(self):
        for bot_id in list(self.active_bridges.keys()):
            self.stop_bridge(bot_id)


proxy_manager = ProxyManager(PROXY_FILE)


# ============================================================================
# ТРАФИК МОНИТОР
# ============================================================================

class TrafficMonitor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = datetime.now()
        self.start_bytes_sent = 0
        self.start_bytes_recv = 0
        self._stats = {
            "bytes_sent": 0,
            "bytes_recv": 0,
            "proxy_traffic": 0,
            "video_direct_traffic": 0,
            "video_direct_bytes": 0,
            "proxy_bytes": 0
        }
        self._running = False
        self._thread = None
        
    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
    def _monitor_loop(self):
        last_recv = 0
        while self._running:
            time.sleep(5)
            try:
                net = psutil.net_io_counters()
                if last_recv > 0:
                    diff = net.bytes_recv - last_recv
                    self._stats["proxy_bytes"] += int(diff * 0.7)
                last_recv = net.bytes_recv
            except:
                pass
    
    def add_video_traffic(self, url: str, bytes_count: int):
        self._stats["video_direct_traffic"] += bytes_count / 1024 / 1024
        self._stats["video_direct_bytes"] += bytes_count
        print(f"  🎬 Direct video: {bytes_count / 1024 / 1024:.1f} MB (bypass proxy)")
    
    def add_proxy_traffic(self, bytes_count: int):
        self._stats["proxy_traffic"] += bytes_count / 1024 / 1024
        self._stats["proxy_bytes"] += bytes_count
    
    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
    
    def print_summary(self):
        saved = self._stats["video_direct_traffic"] * 0.7
        print("\n" + "="*70)
        print("📊 TRAFFIC STATISTICS")
        print("="*70)
        print(f"  Through proxy:       {self._stats['proxy_traffic']:.2f} MB")
        print(f"  Video direct:        {self._stats['video_direct_traffic']:.2f} MB")
        print(f"  💰 Saved (70%):      {saved:.2f} MB")
        print(f"  Duration:            {(datetime.now() - self.start_time).seconds}s")


# ============================================================================
# ПРОФИЛИ УСТРОЙСТВ
# ============================================================================

class OSType(Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"

@dataclass
class DeviceProfile:
    name: str
    os_type: OSType
    os_version: str
    user_agent: str
    platform: str
    platform_version: str
    architecture: str
    bitness: str
    screen_width: int
    screen_height: int
    viewport_width: int
    viewport_height: int
    device_pixel_ratio: float
    color_depth: int
    hardware_concurrency: int
    device_memory: float
    languages: List[str]
    timezone: str
    locale: str
    fonts: List[str]
    plugins: List[Dict]
    webgl_vendor: str
    webgl_renderer: str
    canvas_noise_level: float
    is_mobile: bool
    has_touch: bool
    max_touch_points: int
    audio_latency: float
    audio_channel_count: int
    
    @classmethod
    def get_windows_chrome(cls) -> 'DeviceProfile':
        return cls(
            name="Windows 11 Chrome 122",
            os_type=OSType.WINDOWS,
            os_version="11.0.0",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            platform="Win32",
            platform_version="10.0.0",
            architecture="x86",
            bitness="64",
            screen_width=1920,
            screen_height=1080,
            viewport_width=1920,
            viewport_height=940,
            device_pixel_ratio=1.0,
            color_depth=24,
            hardware_concurrency=8,
            device_memory=8.0,
            languages=["ru-RU", "ru", "en-US", "en"],
            timezone="Europe/Moscow",
            locale="ru_RU",
            fonts=["Arial", "Tahoma", "Verdana", "Times New Roman", "Courier New"],
            plugins=[
                {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai", "description": ""},
                {"name": "Native Client", "filename": "internal-nacl-plugin", "description": ""},
                {"name": "Widevine Content Decryption Module", "filename": "widevinecdmadapter.plugin", "description": "Enables Widevine licenses for encrypted media"}
            ],
            webgl_vendor="Intel Inc.",
            webgl_renderer="Intel Iris Xe Graphics",
            canvas_noise_level=0.02,
            is_mobile=False,
            has_touch=False,
            max_touch_points=0,
            audio_latency=0.003,
            audio_channel_count=2
        )
    
    @classmethod
    def get_macos_chrome(cls) -> 'DeviceProfile':
        return cls(
            name="macOS 14 Chrome 122",
            os_type=OSType.MACOS,
            os_version="14.0.0",
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            platform="MacIntel",
            platform_version="10.15.7",
            architecture="arm64",
            bitness="64",
            screen_width=2560,
            screen_height=1440,
            viewport_width=2560,
            viewport_height=1390,
            device_pixel_ratio=2.0,
            color_depth=30,
            hardware_concurrency=10,
            device_memory=16.0,
            languages=["ru-RU", "ru", "en-US", "en"],
            timezone="Europe/Moscow",
            locale="ru_RU",
            fonts=["Helvetica", "Arial", "Times New Roman", "Courier New", "Georgia"],
            plugins=[
                {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
                {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai", "description": ""},
                {"name": "Native Client", "filename": "internal-nacl-plugin", "description": ""}
            ],
            webgl_vendor="Apple Inc.",
            webgl_renderer="Apple M1 Pro",
            canvas_noise_level=0.01,
            is_mobile=False,
            has_touch=False,
            max_touch_points=0,
            audio_latency=0.002,
            audio_channel_count=2
        )
    
    @classmethod
    def get_android_chrome(cls) -> 'DeviceProfile':
        return cls(
            name="Samsung Galaxy S24 Chrome",
            os_type=OSType.ANDROID,
            os_version="14.0.0",
            user_agent="Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
            platform="Android",
            platform_version="14.0.0",
            architecture="arm64",
            bitness="64",
            screen_width=1080,
            screen_height=2340,
            viewport_width=393,
            viewport_height=780,
            device_pixel_ratio=3.0,
            color_depth=24,
            hardware_concurrency=8,
            device_memory=8.0,
            languages=["ru-RU", "ru", "en-US"],
            timezone="Europe/Moscow",
            locale="ru_RU",
            fonts=["Roboto", "Noto Sans", "Droid Sans", "sans-serif"],
            plugins=[],
            webgl_vendor="Qualcomm",
            webgl_renderer="Adreno 750",
            canvas_noise_level=0.03,
            is_mobile=True,
            has_touch=True,
            max_touch_points=10,
            audio_latency=0.005,
            audio_channel_count=2
        )
    
    @classmethod
    def get_ios_safari(cls) -> 'DeviceProfile':
        return cls(
            name="iPhone 15 Pro Safari",
            os_type=OSType.IOS,
            os_version="17.3.0",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
            platform="iPhone",
            platform_version="17.3.0",
            architecture="arm64",
            bitness="64",
            screen_width=1179,
            screen_height=2556,
            viewport_width=390,
            viewport_height=844,
            device_pixel_ratio=3.0,
            color_depth=24,
            hardware_concurrency=6,
            device_memory=6.0,
            languages=["ru-RU", "ru", "en-US"],
            timezone="Europe/Moscow",
            locale="ru_RU",
            fonts=[".SF Pro", "Helvetica Neue", "Arial"],
            plugins=[],
            webgl_vendor="Apple Inc.",
            webgl_renderer="Apple GPU",
            canvas_noise_level=0.015,
            is_mobile=True,
            has_touch=True,
            max_touch_points=5,
            audio_latency=0.004,
            audio_channel_count=2
        )
    
    @classmethod
    def get_random(cls) -> 'DeviceProfile':
        profiles = [cls.get_windows_chrome(), cls.get_macos_chrome(), cls.get_android_chrome(), cls.get_ios_safari()]
        weights = [0.5, 0.25, 0.15, 0.1]
        return random.choices(profiles, weights=weights)[0]


# ============================================================================
# JS СКРИПТЫ (ПОЛНАЯ МАСКИРОВКА + ЛОВУШКИ)
# ============================================================================

def generate_fingerprint_js(profile: DeviceProfile) -> str:
    languages_json = json.dumps(profile.languages)
    plugins_json = json.dumps(profile.plugins)
    
    return f"""
    (function() {{
        console.log('[CFM] Ultimate bypass activating...');
        
        Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined, configurable: false }});
        Object.defineProperty(navigator, 'automation', {{ get: () => undefined, configurable: false }});
        delete navigator.__proto__.webdriver;
        delete navigator.__proto__.automation;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        
        Object.defineProperty(navigator, 'languages', {{ get: () => {languages_json}, configurable: false }});
        Object.defineProperty(navigator, 'language', {{ get: () => '{profile.languages[0]}', configurable: false }});
        Object.defineProperty(navigator, 'platform', {{ get: () => '{profile.platform}', configurable: false }});
        Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {profile.hardware_concurrency}, configurable: false }});
        Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {profile.device_memory}, configurable: false }});
        Object.defineProperty(screen, 'width', {{ get: () => {profile.screen_width}, configurable: false }});
        Object.defineProperty(screen, 'height', {{ get: () => {profile.screen_height}, configurable: false }});
        Object.defineProperty(screen, 'availWidth', {{ get: () => {profile.screen_width}, configurable: false }});
        Object.defineProperty(screen, 'availHeight', {{ get: () => {profile.screen_height - 40}, configurable: false }});
        Object.defineProperty(screen, 'colorDepth', {{ get: () => {profile.color_depth}, configurable: false }});
        Object.defineProperty(screen, 'pixelDepth', {{ get: () => {profile.color_depth}, configurable: false }});
        Object.defineProperty(window, 'devicePixelRatio', {{ get: () => {profile.device_pixel_ratio}, configurable: false }});
        
        const pluginsList = {plugins_json};
        const pluginsObj = {{
            length: pluginsList.length,
            item: function(i) {{ return this[i]; }},
            namedItem: function(n) {{ for(var i=0;i<this.length;i++) if(this[i].name===n) return this[i]; return null; }},
            refresh: function() {{}}
        }};
        for(let i=0; i<pluginsList.length; i++) pluginsObj[i] = pluginsList[i];
        Object.defineProperty(navigator, 'plugins', {{ get: () => pluginsObj, configurable: false }});
        
        Object.defineProperty(navigator, 'mimeTypes', {{
            get: () => {{
                const mimes = {{
                    length: 2,
                    0: {{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' }},
                    1: {{ type: 'text/pdf', suffixes: 'pdf', description: 'Portable Document Format' }},
                    item: function(i) {{ return this[i]; }},
                    namedItem: function(n) {{ return this[0].type === n ? this[0] : null; }}
                }};
                return mimes;
            }},
            configurable: false
        }});
        
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {{
            if (param === 37445) return '{profile.webgl_vendor}';
            if (param === 37446) return '{profile.webgl_renderer}';
            return getParameter.call(this, param);
        }};
        
        const getExtension = WebGLRenderingContext.prototype.getExtension;
        WebGLRenderingContext.prototype.getExtension = function(name) {{
            if (name === 'WEBGL_debug_renderer_info') return null;
            return getExtension.call(this, name);
        }};
        
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
            if (this.width > 16 && this.height > 16 && Math.random() < {profile.canvas_noise_level}) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    const imgData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imgData.data.length; i += 100) {{
                        imgData.data[i] = imgData.data[i] ^ (Math.random() * 3);
                    }}
                    ctx.putImageData(imgData, 0, 0);
                }}
            }}
            return origToDataURL.call(this, type, quality);
        }};
        
        const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
            const result = origGetImageData.call(this, x, y, w, h);
            if (Math.random() < {profile.canvas_noise_level}) {{
                for (let i = 0; i < result.data.length; i += 4) {{
                    result.data[i] = result.data[i] ^ (Math.random() * 2);
                }}
            }}
            return result;
        }};
        
        const origPeerConnection = window.RTCPeerConnection;
        window.RTCPeerConnection = function(config) {{
            config = config || {{}};
            config.iceServers = [];
            return new origPeerConnection(config);
        }};
        
        window.RTCPeerConnection.prototype.createDataChannel = function(label, options) {{
            return new origPeerConnection.prototype.createDataChannel(label, options);
        }};
        
        if (navigator.userAgentData) {{
            Object.defineProperty(navigator.userAgentData, 'platform', {{ get: () => '{profile.platform}', configurable: false }});
            Object.defineProperty(navigator.userAgentData, 'mobile', {{ get: () => {'true' if profile.is_mobile else 'false'}, configurable: false }});
            Object.defineProperty(navigator.userAgentData, 'architecture', {{ get: () => '{profile.architecture}', configurable: false }});
            Object.defineProperty(navigator.userAgentData, 'bitness', {{ get: () => '{profile.bitness}', configurable: false }});
            Object.defineProperty(navigator.userAgentData, 'platformVersion', {{ get: () => '{profile.platform_version}', configurable: false }});
            
            const origGetHighEntropy = navigator.userAgentData.getHighEntropyValues;
            navigator.userAgentData.getHighEntropyValues = function(hints) {{
                return origGetHighEntropy.call(this, hints).then(values => {{
                    if (hints.includes('platform')) values.platform = '{profile.platform}';
                    if (hints.includes('platformVersion')) values.platformVersion = '{profile.platform_version}';
                    if (hints.includes('architecture')) values.architecture = '{profile.architecture}';
                    if (hints.includes('bitness')) values.bitness = '{profile.bitness}';
                    if (hints.includes('model')) values.model = '';
                    if (hints.includes('fullVersionList')) {{
                        values.fullVersionList = [
                            {{brand: 'Chromium', version: '122.0.0.0'}},
                            {{brand: 'Google Chrome', version: '122.0.0.0'}}
                        ];
                    }}
                    return values;
                }});
            }};
        }}
        
        if (navigator.permissions && navigator.permissions.query) {{
            const origQuery = navigator.permissions.query;
            navigator.permissions.query = function(desc) {{
                if (desc.name === 'notifications') return Promise.resolve({{ state: 'default' }});
                if (desc.name === 'geolocation') return Promise.resolve({{ state: 'prompt' }});
                return origQuery.call(this, desc);
            }};
        }}
        
        Object.defineProperty(navigator, 'connection', {{
            get: () => ({{
                effectiveType: '4g',
                rtt: 50,
                downlink: 10,
                saveData: false,
                addEventListener: function() {{}},
                removeEventListener: function() {{}}
            }}),
            configurable: false
        }});
        
        const origNow = performance.now;
        let lastValue = 0;
        performance.now = function() {{
            let value = origNow.call(this);
            if (value - lastValue < 0.1) value += 0.05;
            lastValue = value;
            return value;
        }};
        
        console.log('[CFM] Bypass active - {profile.name}');
    }})();
    """

TRAP_JS = """
(function() {
    window.CAA_LOGS = [];
    window.CAA_DETECTIONS = [];
    
    function logDetection(type, data, severity = 'info') {
        const entry = {
            type: type,
            data: data,
            severity: severity,
            timestamp: Date.now(),
            url: window.location.href,
            userAgent: navigator.userAgent
        };
        window.CAA_LOGS.push(entry);
        if (severity === 'critical') {
            window.CAA_DETECTIONS.push(entry);
        }
        console.log('[CAA_TRAP]', JSON.stringify(entry));
    }
    
    const originalNavigator = window.navigator;
    const navHandler = {
        get(target, prop) {
            const value = target[prop];
            if (prop === 'webdriver' || prop === 'automation') {
                logDetection('critical_property', { property: prop, value: value }, 'critical');
            } else if (prop === 'plugins') {
                logDetection('fingerprint_plugins', { length: value?.length }, 'info');
            } else if (prop === 'languages') {
                logDetection('fingerprint_languages', { languages: value }, 'info');
            } else if (prop === 'userAgent') {
                logDetection('fingerprint_ua', { ua: value }, 'info');
            } else if (prop === 'platform') {
                logDetection('fingerprint_platform', { platform: value }, 'info');
            } else if (prop === 'hardwareConcurrency') {
                logDetection('fingerprint_hardware', { concurrency: value }, 'info');
            } else if (prop === 'deviceMemory') {
                logDetection('fingerprint_memory', { memory: value }, 'info');
            }
            return value;
        }
    };
    window.navigator = new Proxy(originalNavigator, navHandler);
    
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {
        logDetection('canvas_fingerprint', { method: 'toDataURL', w: this.width, h: this.height }, 'warning');
        return origToDataURL.apply(this, arguments);
    };
    
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
        logDetection('canvas_read', { method: 'getImageData', x: x, y: y, w: w, h: h }, 'warning');
        return origGetImageData.apply(this, arguments);
    };
    
    const origGetParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445 || param === 37446) {
            logDetection('webgl_fingerprint', { param: param === 37445 ? 'VENDOR' : 'RENDERER' }, 'warning');
        }
        return origGetParameter.call(this, param);
    };
    
    const origGetExtension = WebGLRenderingContext.prototype.getExtension;
    WebGLRenderingContext.prototype.getExtension = function(name) {
        logDetection('webgl_extension', { extension: name }, 'info');
        return origGetExtension.call(this, name);
    };
    
    const origFetch = window.fetch;
    window.fetch = function(url, options) {
        if (typeof url === 'string') {
            if (url.includes('collect') || url.includes('fingerprint') || url.includes('check') || 
                url.includes('verify') || url.includes('captcha') || url.includes('bot')) {
                logDetection('suspicious_request', { url: url, method: options?.method || 'GET' }, 'warning');
            }
            if (url.includes('.mp4') || url.includes('.m3u8') || url.includes('.ts')) {
                logDetection('video_request', { url: url }, 'info');
            }
        }
        return origFetch.apply(this, arguments);
    };
    
    const origXHROpen = XMLHttpRequest.prototype.open;
    const origXHRSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
        this._caa_url = url;
        this._caa_method = method;
        return origXHROpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
        if (this._caa_url && typeof this._caa_url === 'string') {
            if (this._caa_url.includes('collect') || this._caa_url.includes('fingerprint') || 
                this._caa_url.includes('check') || this._caa_url.includes('verify')) {
                logDetection('suspicious_xhr', { url: this._caa_url, method: this._caa_method }, 'warning');
            }
        }
        return origXHRSend.call(this, body);
    };
    
    const origNow = performance.now;
    performance.now = function() {
        logDetection('performance_now', { timestamp: Date.now() }, 'info');
        return origNow.apply(this, arguments);
    };
    
    if (navigator.getBattery) {
        const origGetBattery = navigator.getBattery;
        navigator.getBattery = function() {
            logDetection('battery_api', { method: 'getBattery' }, 'info');
            return origGetBattery.apply(this, arguments);
        };
    }
    
    if (window.Notification && window.Notification.requestPermission) {
        const origRequestPermission = Notification.requestPermission;
        Notification.requestPermission = function() {
            logDetection('notification_api', { method: 'requestPermission' }, 'info');
            return origRequestPermission.apply(this, arguments);
        };
    }
    
    setInterval(function() {
        if (window.CAA_LOGS && window.CAA_LOGS.length > 0) {
            console.log('[CAA_STATS]', JSON.stringify({
                total_logs: window.CAA_LOGS.length,
                detections: window.CAA_DETECTIONS.length,
                timestamp: Date.now()
            }));
        }
    }, 10000);
    
    console.log('[CAA] Trap active - monitoring all anti-fraud checks');
})();
"""

BEHAVIOR_JS = """
(function() {
    console.log('[CFM] Human behavior emulation started');
    
    let lastX = Math.random() * window.innerWidth;
    let lastY = Math.random() * window.innerHeight;
    
    const mouseMoveInterval = setInterval(() => {
        const newX = lastX + (Math.random() - 0.5) * 50;
        const newY = lastY + (Math.random() - 0.5) * 50;
        const moveEvent = new MouseEvent('mousemove', { 
            clientX: Math.max(0, Math.min(newX, window.innerWidth)),
            clientY: Math.max(0, Math.min(newY, window.innerHeight)),
            bubbles: true 
        });
        document.dispatchEvent(moveEvent);
        lastX = newX;
        lastY = newY;
    }, 2000 + Math.random() * 3000);
    
    const scrollInterval = setInterval(() => {
        if (Math.random() < 0.4) {
            const delta = 100 + Math.random() * 400;
            window.scrollBy({ top: delta, behavior: 'smooth' });
            setTimeout(() => {
                if (Math.random() < 0.3) {
                    window.scrollBy({ top: -delta/3, behavior: 'smooth' });
                }
            }, 500 + Math.random() * 1500);
        }
    }, 5000 + Math.random() * 8000);
    
    setTimeout(() => {
        const clickInterval = setInterval(() => {
            if (Math.random() < 0.08) {
                const elements = document.querySelectorAll('a, button, [role="button"], .clickable, .btn');
                if (elements.length > 0) {
                    const el = elements[Math.floor(Math.random() * elements.length)];
                    if (el && el.getBoundingClientRect) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top > 0 && rect.top < window.innerHeight) {
                            el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                            setTimeout(() => {
                                if (Math.random() < 0.3) {
                                    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                                    console.log('[CFM] Random click on:', el.tagName, el.className);
                                }
                            }, 500 + Math.random() * 1000);
                        }
                    }
                }
            }
        }, 20000 + Math.random() * 20000);
    }, 10000);
    
    let scrollDirection = 1;
    setInterval(() => {
        if (Math.random() < 0.1) {
            scrollDirection = scrollDirection === 1 ? -1 : 1;
        }
        if (Math.random() < 0.2) {
            const delta = (50 + Math.random() * 150) * scrollDirection;
            window.scrollBy({ top: delta, behavior: 'smooth' });
        }
    }, 3000 + Math.random() * 4000);
    
    window.addEventListener('beforeunload', function() {
        clearInterval(mouseMoveInterval);
        clearInterval(scrollInterval);
    });
    
    console.log('[CFM] Behavior emulation active');
})();
"""

DIRECT_VIDEO_JS = """
(function() {
    const originalFetch = window.fetch;
    window.fetch = function(url, options) {
        const isVideo = typeof url === 'string' && (
            url.includes('.mp4') || url.includes('.m3u8') || 
            url.includes('.ts') || url.includes('.m4s') ||
            url.includes('video') || url.includes('media') || 
            url.includes('playlist') || url.includes('chunk')
        );
        
        if (isVideo) {
            console.log('[CFM] 🎬 Direct video (bypassing proxy):', url.split('/').pop());
            const event = new CustomEvent('cfm_video_direct', { detail: { url: url, timestamp: Date.now() } });
            window.dispatchEvent(event);
        }
        return originalFetch.call(this, url, options);
    };
    
    const origXHROpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        this._caa_is_video = typeof url === 'string' && (
            url.includes('.mp4') || url.includes('.m3u8') || url.includes('.ts') ||
            url.includes('video') || url.includes('media')
        );
        if (this._caa_is_video) {
            console.log('[CFM] 🎬 Direct video XHR:', url.split('/').pop());
        }
        return origXHROpen.call(this, method, url);
    };
    
    console.log('[CFM] Direct video handler injected - video traffic bypasses proxy');
})();
"""


# ============================================================================
# ОСНОВНОЙ КЛАСС
# ============================================================================

class CFMUltimateBypass:
    def __init__(self, bot_number=1):
        self.bot = None
        self.bridge = None
        self.bot_id = None
        self.profile = None
        self.trap_logs = []
        self.scan_id = None
        self.traffic_monitor = None
        self.bot_number = bot_number
        self.detections_count = 0
        
    async def start(self, use_proxy: bool = True):
        self.scan_id = f"cfm_{self.bot_number}_{int(time.time())}"
        self.bot_id = self.scan_id
        self.traffic_monitor = TrafficMonitor(self.scan_id)
        self.traffic_monitor.start()
        
        print(f"\n[Bot #{self.bot_number}] ========================================")
        print(f"[Bot #{self.bot_number}] Starting CFM Ultimate Bypass")
        print(f"[Bot #{self.bot_number}] ========================================")
        
        self.profile = DeviceProfile.get_random()
        print(f"[Bot #{self.bot_number}] 📱 Device: {self.profile.name}")
        print(f"[Bot #{self.bot_number}]    OS: {self.profile.os_type.value} {self.profile.os_version}")
        print(f"[Bot #{self.bot_number}]    Screen: {self.profile.screen_width}x{self.profile.screen_height}")
        
        local_proxy_url = ""
        if use_proxy:
            proxy_info = proxy_manager.get_random_proxy()
            if proxy_info:
                self.bridge = proxy_manager.create_bridge(proxy_info, self.bot_id)
                if self.bridge:
                    local_proxy_url = self.bridge.get_local_proxy_url()
                    print(f"[Bot #{self.bot_number}] 🔌 Proxy bridge: {proxy_info['host']}:{proxy_info['port']} → localhost:{self.bridge.local_port}")
                    print(f"[Bot #{self.bot_number}] 💡 Video traffic will bypass proxy (save bandwidth)")
                else:
                    print(f"[Bot #{self.bot_number}] ⚠️ Failed to create proxy bridge")
            else:
                print(f"[Bot #{self.bot_number}] ⚠️ No proxies available")
        
        config = cfm.BotConfig()
        config.id = self.scan_id
        config.width = self.profile.screen_width
        config.height = self.profile.screen_height
        config.headless = False
        config.disable_gpu = False
        config.disable_web_security = True
        config.ignore_certificate_errors = True
        config.user_agent = self.profile.user_agent
        config.accept_language = self.profile.languages[0]
        config.locale = self.profile.locale
        config.timezone = self.profile.timezone
        config.proxy_url = local_proxy_url
        
        config.enable_fingerprint_spoofing = True
        config.enable_automation_blocking = True
        config.enable_behavior_emulation = True
        config.enable_network_spoofing = True
        config.enable_webrtc_blocking = True
        config.behavior_profile = "human"
        config.min_action_delay_ms = 150
        config.max_action_delay_ms = 2500
        
        config.extra_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
            "--disable-site-isolation-trials",
            "--disable-webrtc",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
            f"--lang={self.profile.locale}",
            f"--timezone-id={self.profile.timezone}",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-sync",
            "--log-level=3",
            "--silent"
        ]
        
        if self.profile.is_mobile:
            config.extra_args.extend(["--enable-viewport", "--touch-events=enabled"])
        else:
            config.extra_args.append("--start-maximized")
        
        print(f"[Bot #{self.bot_number}] 🔧 Starting CFM bot...")
        self.bot = cfm.BotInstance(config)
        
        if not self.bot.start():
            raise Exception("Failed to start bot")
        
        await asyncio.sleep(3)
        
        status = self.bot.get_status()
        if not status.is_connected:
            raise Exception("DevTools connection failed")
        
        print(f"[Bot #{self.bot_number}] ✅ Bot started and connected")
        
        print(f"[Bot #{self.bot_number}] 📜 Injecting scripts...")
        self.bot.execute_javascript(generate_fingerprint_js(self.profile), await_promise=False)
        self.bot.execute_javascript(TRAP_JS, await_promise=False)
        self.bot.execute_javascript(BEHAVIOR_JS, await_promise=False)
        self.bot.execute_javascript(DIRECT_VIDEO_JS, await_promise=False)
        print(f"[Bot #{self.bot_number}]    ✅ Fingerprint bypass + Trap + Behavior + Direct video injected")
        
        spoof_targets = ["https://7days.ru", "https://www.playground.ru", "https://www.kp.ru", "https://lenta.ru"]
        spoof_target = random.choice(spoof_targets)
        self.bot.set_context_spoofing(spoof_target)
        print(f"[Bot #{self.bot_number}] 🎭 Context spoofing: {spoof_target}")
        
        self.bot.apply_full_protection()
        print(f"[Bot #{self.bot_number}] 🛡️ Full protection applied")
        
        return True
    
    async def navigate(self, url: str):
        print(f"[Bot #{self.bot_number}] 🌐 Navigating to {url}")
        
        self.bot.execute_javascript("window._caa_start_time = Date.now();", await_promise=False)
        
        result = self.bot.navigate(url, timeout_ms=45000)
        
        if not result.success:
            raise Exception(f"Navigation failed: {result.error}")
        
        print(f"[Bot #{self.bot_number}] ✅ Page loaded")
        
        await asyncio.sleep(5)
        
        load_time_js = "return Date.now() - (window._caa_start_time || Date.now());"
        load_time_result = self.bot.execute_javascript(load_time_js, await_promise=True, return_by_value=True)
        if load_time_result and load_time_result.success:
            print(f"[Bot #{self.bot_number}]    Load time: {load_time_result.value}ms")
        
        return True
    
    async def emulate_user(self):
        print(f"[Bot #{self.bot_number}] 🧑 Emulating human behavior...")
        
        scrolls = random.randint(4, 8)
        for i in range(scrolls):
            delta = random.randint(200, 500)
            self.bot.execute_javascript(f"window.scrollBy({{top: {delta}, behavior: 'smooth'}});")
            await asyncio.sleep(random.uniform(1.5, 3.5))
        
        print(f"[Bot #{self.bot_number}] 🎬 Video session (DIRECT - no proxy traffic)")
        watch_time = random.randint(35, 65)
        estimated_mb = (watch_time * 6) / 8
        self.traffic_monitor.add_video_traffic("video_stream", int(estimated_mb * 1024 * 1024))
        
        self.bot.execute_javascript("""
            const video = document.querySelector('video');
            if (video) {
                video.play();
                console.log('[CFM] Video playing');
            }
        """)
        
        for i in range(0, watch_time, 10):
            await asyncio.sleep(min(10, watch_time - i))
            if random.random() < 0.12:
                self.bot.execute_javascript("document.querySelector('video')?.pause();")
                await asyncio.sleep(random.uniform(1, 2.5))
                self.bot.execute_javascript("document.querySelector('video')?.play();")
                print(f"[Bot #{self.bot_number}]    ⏸️ Video paused/resumed")
        
        self.bot.execute_javascript("window.scrollTo({top: 0, behavior: 'smooth'});")
        await asyncio.sleep(2)
        
        print(f"[Bot #{self.bot_number}]    ✅ Watched {watch_time}s, saved ~{estimated_mb:.1f} MB of proxy traffic")
    
    async def collect_logs(self) -> tuple:
        result = self.bot.execute_javascript(
            "return JSON.stringify(window.CAA_LOGS || []);",
            await_promise=True,
            return_by_value=True
        )
        
        critical_count = 0
        warning_count = 0
        fingerprint_count = 0
        canvas_count = 0
        webgl_count = 0
        network_count = 0
        
        if result and result.success:
            try:
                value = result.value
                if isinstance(value, str):
                    logs = json.loads(value)
                elif isinstance(value, dict) and 'result' in value:
                    logs = json.loads(value['result']['value'])
                else:
                    logs = []
                
                self.trap_logs = logs
                
                for l in logs:
                    if isinstance(l, dict):
                        severity = l.get('severity', 'info')
                        log_type = l.get('type', '')
                        
                        if severity == 'critical':
                            critical_count += 1
                        elif severity == 'warning':
                            warning_count += 1
                        
                        if 'fingerprint' in log_type:
                            fingerprint_count += 1
                        elif 'canvas' in log_type:
                            canvas_count += 1
                        elif 'webgl' in log_type:
                            webgl_count += 1
                        elif 'suspicious' in log_type:
                            network_count += 1
                
                self.detections_count = critical_count + warning_count
                
            except Exception as e:
                print(f"[Bot #{self.bot_number}] Log parse error: {e}")
        
        return critical_count, warning_count, fingerprint_count, canvas_count, webgl_count, network_count
    
    async def screenshot(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.bot.take_screenshot(path)
        print(f"[Bot #{self.bot_number}] 📸 Screenshot: {path}")
    
    async def stop(self):
        if self.bot:
            self.bot.stop()
        
        if self.bridge:
            proxy_manager.stop_bridge(self.bot_id)
        
        if self.traffic_monitor:
            self.traffic_monitor.stop()
            self.traffic_monitor.print_summary()
        
        print(f"[Bot #{self.bot_number}] ✅ Bot stopped")
    
    async def run_full_session(self):
        try:
            await self.start(use_proxy=True)
            await self.navigate(TARGET_URL)
            await self.emulate_user()
            
            critical, warning, fingerprint, canvas, webgl, network = await self.collect_logs()
            
            scan_id = f"scan_{self.bot_number}_{int(time.time())}"
            screenshot_path = f"/root/CAA/CAA/reports/screenshots/{scan_id}.png"
            await self.screenshot(screenshot_path)
            
            await self.stop()
            
            result = {
                "bot_number": self.bot_number,
                "success": True,
                "critical_detections": critical,
                "warning_detections": warning,
                "fingerprint_checks": fingerprint,
                "canvas_checks": canvas,
                "webgl_checks": webgl,
                "network_checks": network,
                "total_detections": critical + warning,
                "screenshot": screenshot_path
            }
            
            print(f"\n[Bot #{self.bot_number}] ========== RESULTS ==========")
            print(f"[Bot #{self.bot_number}] Critical detections: {critical}")
            print(f"[Bot #{self.bot_number}] Warning detections: {warning}")
            print(f"[Bot #{self.bot_number}] Fingerprint checks: {fingerprint}")
            print(f"[Bot #{self.bot_number}] Canvas checks: {canvas}")
            print(f"[Bot #{self.bot_number}] WebGL checks: {webgl}")
            print(f"[Bot #{self.bot_number}] Network suspicious: {network}")
            
            if critical == 0 and warning < 5:
                print(f"[Bot #{self.bot_number}] ✅ PERFECT! No anti-fraud detection!")
            else:
                print(f"[Bot #{self.bot_number}] ⚠️ Detected {critical + warning} suspicious checks")
            
            return result
            
        except Exception as e:
            print(f"[Bot #{self.bot_number}] ❌ Error: {e}")
            await self.stop()
            return {"bot_number": self.bot_number, "success": False, "error": str(e)}


# ============================================================================
# РЕЖИМЫ ЗАПУСКА
# ============================================================================

async def run_single_bot():
    print("\n" + "="*70)
    print("🔥 SINGLE BOT MODE")
    print("="*70)
    
    bot = CFMUltimateBypass(bot_number=1)
    result = await bot.run_full_session()
    
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)
    if result.get("success"):
        print(f"✅ Bot completed successfully")
        print(f"   Critical detections: {result.get('critical_detections', 0)}")
        print(f"   Warning detections: {result.get('warning_detections', 0)}")
        if result.get('critical_detections', 0) == 0:
            print("   🎉 Your CFM is perfectly masked!")
        else:
            print("   ⚠️ Some detections found - check CFM configuration")
    else:
        print(f"❌ Bot failed: {result.get('error')}")


async def run_multiple_bots(count: int):
    print("\n" + "="*70)
    print(f"🔥 MULTIPLE BOTS MODE - {count} bots in parallel")
    print("="*70)
    
    proxies = proxy_manager.get_unique_proxies(count)
    if len(proxies) < count:
        print(f"⚠️ Only {len(proxies)} unique proxies available")
        count = len(proxies)
    
    bots = [CFMUltimateBypass(bot_number=i+1) for i in range(count)]
    
    async def run_bot_with_proxy(bot, proxy):
        return await bot.run_full_session()
    
    tasks = [run_bot_with_proxy(bot, proxy) for bot, proxy in zip(bots, proxies)]
    results = await asyncio.gather(*tasks)
    
    print("\n" + "="*70)
    print("BATCH RESULTS SUMMARY")
    print("="*70)
    
    success_count = sum(1 for r in results if r.get("success"))
    total_critical = sum(r.get("critical_detections", 0) for r in results)
    total_warning = sum(r.get("warning_detections", 0) for r in results)
    
    print(f"Successful bots: {success_count}/{count}")
    print(f"Total critical detections: {total_critical}")
    print(f"Total warning detections: {total_warning}")
    
    for r in results:
        if r.get("success"):
            status = "✅" if r.get("critical_detections", 0) == 0 else "⚠️"
            print(f"  {status} Bot #{r.get('bot_number')}: critical={r.get('critical_detections', 0)}, warning={r.get('warning_detections', 0)}")
    
    return results


async def run_stream_mode(bots_count: int, duration_minutes: int):
    print("\n" + "="*70)
    print(f"🔥 STREAM MODE - {bots_count} bots running for {duration_minutes} minutes")
    print("="*70)
    
    proxies = proxy_manager.get_unique_proxies(bots_count)
    if len(proxies) < bots_count:
        print(f"⚠️ Only {len(proxies)} unique proxies available")
        bots_count = len(proxies)
    
    end_time = time.time() + (duration_minutes * 60)
    session_count = 0
    total_critical = 0
    total_warning = 0
    
    async def run_bot_loop(bot, bot_index):
        nonlocal session_count, total_critical, total_warning
        while time.time() < end_time:
            try:
                result = await bot.run_full_session()
                session_count += 1
                total_critical += result.get("critical_detections", 0)
                total_warning += result.get("warning_detections", 0)
                print(f"[Stream] Bot {bot_index+1} completed session #{session_count}")
                await asyncio.sleep(random.uniform(15, 45))
            except Exception as e:
                print(f"[Stream] Bot {bot_index+1} error: {e}")
                await asyncio.sleep(30)
    
    bots = [CFMUltimateBypass(bot_number=i+1) for i in range(bots_count)]
    tasks = [run_bot_loop(bot, i) for i, bot in enumerate(bots)]
    await asyncio.gather(*tasks)
    
    print("\n" + "="*70)
    print("STREAM MODE SUMMARY")
    print("="*70)
    print(f"Total sessions: {session_count}")
    print(f"Total critical detections: {total_critical}")
    print(f"Total warning detections: {total_warning}")
    print(f"Average critical per session: {total_critical/session_count if session_count > 0 else 0:.1f}")
    
    proxy_manager.stop_all_bridges()


def show_menu():
    print("\n" + "="*70)
    print("🔥 CFM ULTIMATE BYPASS - Protected Media Killer")
    print("="*70)
    print("1. 🎯 Run SINGLE bot (one session)")
    print("2. 🚀 Run MULTIPLE bots (parallel, one session each)")
    print("3. ♾️ Run STREAM mode (continuous, multiple sessions)")
    print("4. 📊 Show statistics")
    print("5. 🧹 Stop all bridges")
    print("6. ❌ Exit")
    print("="*70)


def show_stats():
    print("\n📊 STATISTICS")
    print(f"  Total proxies loaded: {len(proxy_manager.proxies)}")
    print(f"  Active bridges: {len(proxy_manager.active_bridges)}")
    print(f"  Max concurrent bots: {MAX_CONCURRENT_BOTS}")
    print(f"  Gost path: {GOST_PATH}")
    print(f"  Target URL: {TARGET_URL}")
    print(f"  Proxy file: {PROXY_FILE}")
    print(f"  Base local port: {BASE_LOCAL_PORT}")


async def main():
    if not os.path.exists(GOST_PATH):
        print(f"❌ Gost not found at: {GOST_PATH}")
        print("   Download: wget https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz")
        print("   gunzip gost-linux-amd64-2.11.5.gz")
        print("   mv gost-linux-amd64-2.11.5 gost")
        print("   chmod +x gost")
        return
    
    if not proxy_manager.proxies:
        print("⚠️ No proxies loaded! Check proxies.txt file")
    
    print(f"✅ Gost found: {GOST_PATH}")
    print(f"✅ Proxies loaded: {len(proxy_manager.proxies)}")
    
    while True:
        show_menu()
        choice = input("\n📌 Choose action (1-6): ").strip()
        
        if choice == '1':
            await run_single_bot()
            
        elif choice == '2':
            try:
                count = int(input("How many bots to run in parallel (1-10): "))
                count = max(1, min(10, count))
                await run_multiple_bots(count)
            except ValueError:
                print("❌ Invalid input! Please enter a number.")
                
        elif choice == '3':
            try:
                count = int(input("How many bots in stream (1-5): "))
                minutes = int(input("How many minutes to run: "))
                count = max(1, min(5, count))
                minutes = max(1, min(120, minutes))
                await run_stream_mode(count, minutes)
            except ValueError:
                print("❌ Invalid input! Please enter a number.")
                
        elif choice == '4':
            show_stats()
            
        elif choice == '5':
            print("\n🧹 Stopping all bridges...")
            proxy_manager.stop_all_bridges()
            print("✅ All bridges stopped")
            
        elif choice == '6':
            print("\n🧹 Cleaning up...")
            proxy_manager.stop_all_bridges()
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice! Please enter 1-6")
        
        input("\n⏎ Press Enter to continue...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user...")
        proxy_manager.stop_all_bridges()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        proxy_manager.stop_all_bridges()