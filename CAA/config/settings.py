import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
REPORTS_DIR = BASE_DIR / "reports"
RAW_LOGS_DIR = REPORTS_DIR / "raw"
ANALYZED_DIR = REPORTS_DIR / "analyzed"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
PROFILES_DIR = BASE_DIR / "profiles"

for dir_path in [RAW_LOGS_DIR, ANALYZED_DIR, SCREENSHOTS_DIR, PROFILES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

CFM_CONFIG = {
    "binary_path": os.getenv("CFM_PATH", "/root/CFM/cpp_core/build/lib/libcfm_core.so"),
    "lib_path": "/root/CFM/cpp_core/build/lib",
    "headless": os.getenv("HEADLESS", "false").lower() == "true",
    "timeout_seconds": 30,
    "navigation_timeout": 10,
    "preload_scripts": [
        BASE_DIR / "js" / "trap_injected.js",
        BASE_DIR / "js" / "canvas_trap.js",
        BASE_DIR / "js" / "network_trap.js",
        BASE_DIR / "js" / "behavior_trap.js"
    ]
}

SCANNER_CONFIG = {
    "wait_before_collect": 15,
    "wait_for_network_idle": 3,
    "max_retries": 3,
    "screenshot_on_block": True,
    "collect_stack_traces": True
}

ANALYZER_CONFIG = {
    "use_heuristics": True,
    "ml_enabled": False,
    "triggers_db_path": BASE_DIR / "config" / "triggers_db.json",
    "comparison_threshold": 0.7,
    "export_formats": ["json", "html"]
}

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": BASE_DIR / "logs" / "caa.log"
}

TEST_URLS = {
    "protected_media_test": "https://videoplayer.mediavi.ru/",
    "cloudflare_test": "https://www.cloudflare.com/cdn-cgi/trace",
    "custom": os.getenv("TEST_URL", "")
}

AVAILABLE_PROFILES = {
    "clean": PROFILES_DIR / "clean_chrome.json",
    "cfm_default": PROFILES_DIR / "cfm_default.json",
    "cfm_stealth": PROFILES_DIR / "cfm_stealth.json"
}

CFM_METRIC_PATH = "/root/CFM/cpp_core/build/metric.py"
CFM_PROXIES_PATH = "/root/CFM/cpp_core/build/proxies.txt"
CFM_GOST_PATH = "/root/CFM/cpp_core/build/gost"