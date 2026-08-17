#!/usr/bin/env python3
"""Run the Asana sync repeatedly for local development."""

import os
import time

from asana_sync import main


def run() -> None:
    interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "900"))
    while True:
        try:
            main()
        except Exception as error:
            print(f"Sync failed: {error}", flush=True)
        print(f"Next sync in {interval // 60} minutes", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    run()
