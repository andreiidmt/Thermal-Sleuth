"""
Thermal Sleuth - Continuous Monitoring Scheduler
Polls Copernicus every 30 minutes for new Sentinel-3 SLSTR passes
and runs the anomaly detection pipeline on new data.
"""
import time
import threading
from datetime import datetime, timezone
from satellite_engine.config import POLL_INTERVAL_SECONDS
from satellite_engine.pipeline import run_pipeline, run_latest


class ThermalSleuthScheduler:
    """Continuous monitoring daemon for EU-wide thermal pollution detection."""

    def __init__(self, poll_interval=POLL_INTERVAL_SECONDS, days_back=1, max_products=5, download_mode=True):
        self.poll_interval = poll_interval
        self.days_back = days_back
        self.max_products = max_products
        self.download_mode = download_mode
        self.running = False
        self._thread = None
        self.last_scan_time = None
        self.scan_count = 0
        self.total_anomalies_found = 0

    def start(self):
        """Start the continuous monitoring loop in a background thread."""
        if self.running:
            print("[*] Scheduler is already running.")
            return

        self.running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[*] Scheduler started. Polling every {self.poll_interval}s.")

    def stop(self):
        """Stop the monitoring loop."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[*] Scheduler stopped.")

    def _monitor_loop(self):
        """Main polling loop."""
        while self.running:
            try:
                self._run_scan()
            except Exception as e:
                print(f"[!] Scan error: {e}")

            # Wait for next poll
            for _ in range(self.poll_interval):
                if not self.running:
                    return
                time.sleep(1)

    def _run_scan(self):
        """Execute a single scan cycle."""
        self.scan_count += 1
        self.last_scan_time = datetime.now(timezone.utc)
        print(f"\n[SCAN #{self.scan_count}] {self.last_scan_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

        result = run_pipeline(
            days_back=self.days_back,
            max_products=self.max_products,
            download=self.download_mode,
        )
        if result:
            self.total_anomalies_found += result.get("anomalies", 0)

    def get_status(self):
        """Get current scheduler status."""
        return {
            "running": self.running,
            "last_scan": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "scan_count": self.scan_count,
            "total_anomalies": self.total_anomalies_found,
            "poll_interval_seconds": self.poll_interval,
            "days_back": self.days_back,
            "max_products": self.max_products,
            "download_mode": self.download_mode,
        }


# Singleton instance
_scheduler = None


def get_scheduler():
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ThermalSleuthScheduler()
    return _scheduler


if __name__ == "__main__":
    print("=== Thermal Sleuth - Continuous Monitor ===")
    print("Starting EU-wide thermal pollution monitoring...")
    print("Press Ctrl+C to stop.\n")

    scheduler = get_scheduler()
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\nMonitoring stopped.")
