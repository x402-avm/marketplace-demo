import os
import sys
import gc
import time
import ctypes
import logging
import threading
import urllib.request
import urllib.error
from typing import Tuple, Dict, Any, Optional
import psutil

from app.config import (
    MAX_SYSTEM_RAM_PERCENT,
    PREFLIGHT_RAM_LIMIT_PERCENT,
    MEMORY_CHECK_INTERVAL_SECONDS
)

logger = logging.getLogger("OOMGuard")
logging.basicConfig(level=logging.INFO)

class OOMGuard:
    """
    Fail-Safe System Memory & OOM Protection Watchdog.
    Monitors total Linux system RAM every 200ms.
    - Pre-flight rejection: Rejects incoming heavy operations if system RAM >= 85% or available < 3.0 GB.
    - Emergency shutdown: Auto-shuts down process and kills child backends immediately if system RAM >= 90%
      or available < 1.5 GB to prevent OS kernel freezes, swap thrashing, and laptop lockup.
    """

    def __init__(
        self,
        max_ram_percent: float = MAX_SYSTEM_RAM_PERCENT,
        preflight_limit_percent: float = PREFLIGHT_RAM_LIMIT_PERCENT,
        check_interval: float = MEMORY_CHECK_INTERVAL_SECONDS
    ):
        self.max_ram_percent = max_ram_percent
        self.preflight_limit_percent = preflight_limit_percent
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.last_check_percent: float = 0.0

    @staticmethod
    def get_system_ram_percent() -> float:
        """Get live system RAM utilization percent from psutil."""
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return 0.0

    @staticmethod
    def get_available_memory_bytes() -> int:
        """Get live system available RAM in bytes from psutil."""
        try:
            return psutil.virtual_memory().available
        except Exception:
            return 1024 * 1024 * 1024 * 16

    @staticmethod
    def emergency_memory_purge():
        """Aggressively purge Python and glibc memory allocations."""
        try:
            gc.collect()
            # glibc malloc_trim releases dynamic memory arenas back to the Linux kernel
            libc = ctypes.CDLL("libc.so.6")
            libc.malloc_trim(0)
        except Exception:
            pass

    @staticmethod
    def kill_child_processes():
        """Forcibly kill any child processes (e.g. ComfyUI worker) to instantly release RAM."""
        try:
            current_proc = psutil.Process(os.getpid())
            children = current_proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except Exception:
                    pass
        except Exception:
            pass

        # Also kill any orphan ComfyUI process on port 10099
        try:
            for proc in psutil.process_iter(["pid", "cmdline"]):
                cmd = " ".join(proc.info["cmdline"] or [])
                if "10099" in cmd or ("ComfyUI" in cmd and "main.py" in cmd):
                    try:
                        proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass

    @staticmethod
    def interrupt_comfy_backend():
        """Interrupt active ComfyUI prompt to halt memory surges without killing servers."""
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:10099/interrupt",
                data=b"",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                pass
        except Exception:
            pass

    def check_memory_preflight(self) -> Tuple[bool, str]:
        """
        Pre-flight check before initiating generation or heavy processing.
        Returns (True, "OK") if safe, or (False, reason) if system RAM is critically high.
        """
        ram_pct = self.get_system_ram_percent()
        avail_gb = self.get_available_memory_bytes() / (1024 ** 3)
        self.last_check_percent = ram_pct

        if ram_pct >= self.preflight_limit_percent or avail_gb < 1.5:
            self.emergency_memory_purge()
            # Recheck after purge
            ram_pct = self.get_system_ram_percent()
            avail_gb = self.get_available_memory_bytes() / (1024 ** 3)
            if ram_pct >= self.preflight_limit_percent or avail_gb < 1.5:
                return (
                    False,
                    f"System RAM is critically high ({ram_pct:.1f}% used >= {self.preflight_limit_percent}% limit, {avail_gb:.2f} GB free). "
                    "Operation rejected by OOM Fail-Safe Guard to prevent laptop freeze."
                )

        return (True, "OK")

    def preflight_check(self) -> Tuple[bool, str]:
        """Alias for check_memory_preflight for multi-agent orchestrator."""
        return self.check_memory_preflight()

    def get_status(self) -> Dict[str, Any]:
        """Return current OOM Guard telemetry status."""
        mem = psutil.virtual_memory()
        return {
            "oom_guard_active": self._running,
            "system_ram_used_percent": mem.percent,
            "system_ram_available_gb": round(mem.available / (1024 ** 3), 2),
            "system_ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "preflight_threshold_percent": self.preflight_limit_percent,
            "emergency_shutdown_threshold_percent": self.max_ram_percent,
            "safe_headroom_gb": round(mem.available / (1024 ** 3), 2)
        }

    def emergency_shutdown(self, current_pct: float, avail_gb: float):
        """Forcibly terminate application and all child backends immediately."""
        print(
            f"\n{'='*70}\n"
            f"🚨 EMERGENCY FAIL-SAFE SHUTDOWN TRIGGERED: SYSTEM RAM {current_pct:.1f}% >= {self.max_ram_percent}% ({avail_gb:.2f} GB free)\n"
            "Terminating application and child processes immediately to safeguard operating system stability.\n"
            f"{'='*70}\n",
            file=sys.stderr,
            flush=True
        )
        self.emergency_memory_purge()
        self.kill_child_processes()
        os._exit(101)

    def _watchdog_loop(self):
        """Continuous background watchdog thread checking RAM every check_interval."""
        logger.info(
            f"🛡️  OOM Fail-Safe Watchdog active: monitoring system RAM (Limit: {self.max_ram_percent}%, Interval: {self.check_interval}s)"
        )
        warning_logged = False

        while self._running:
            try:
                mem = psutil.virtual_memory()
                ram_pct = mem.percent
                avail_gb = mem.available / (1024 ** 3)
                self.last_check_percent = ram_pct

                # Warning stage (85%+ or < 2.5GB available)
                if (ram_pct >= 85.0 or avail_gb < 2.5) and not warning_logged:
                    logger.warning(
                        f"⚠️  High memory warning: System RAM at {ram_pct:.1f}% ({avail_gb:.2f} GB available). Triggering preemptive memory trim."
                    )
                    self.emergency_memory_purge()
                    warning_logged = True
                elif ram_pct < 80.0 and avail_gb >= 3.5:
                    warning_logged = False

                # Critical Fail-Safe Trigger (>= max_ram_percent or < 0.6 GB available)
                if ram_pct >= self.max_ram_percent or avail_gb < 0.6:
                    logger.critical(
                        f"🚨 EMERGENCY: System RAM reached {ram_pct:.1f}% (limit {self.max_ram_percent}%, {avail_gb:.2f} GB free)! "
                        "Interrupting active ComfyUI prompt and purging memory to protect system stability!"
                    )
                    self.interrupt_comfy_backend()
                    self.emergency_memory_purge()

                    # Final check: only shut down process if available RAM is critically exhausted (< 0.35 GB)
                    time.sleep(0.5)
                    final_mem = psutil.virtual_memory()
                    if (final_mem.available / (1024 ** 3)) < 0.35:
                        self.emergency_shutdown(final_mem.percent, final_mem.available / (1024 ** 3))

            except Exception as e:
                logger.error(f"Error in OOM Watchdog loop: {e}")

            time.sleep(self.check_interval)

    def start_watchdog(self):
        """Start the background watchdog daemon thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._watchdog_loop, daemon=True, name="OOMWatchdog")
            self._thread.start()

    def stop_watchdog(self):
        """Stop the watchdog thread."""
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            self._thread = None


# Singleton instance for the application
oom_guard = OOMGuard()
