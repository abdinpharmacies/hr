import argparse
from pathlib import Path
import signal
import sys
from threading import Event


def main():
    parser = argparse.ArgumentParser(description="Run only requested Website Product Sync jobs.")
    parser.add_argument("--odoo-root", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--addons-path")
    parser.add_argument("--data-dir")
    parser.add_argument("--logfile")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.odoo_root).resolve()))

    from odoo import netsvc
    from odoo.tools import config

    options = ["-c", args.config, "-d", args.database, "--no-http", "--workers=0", "--max-cron-threads=0"]
    for name in ("addons_path", "data_dir", "logfile"):
        value = getattr(args, name)
        if value:
            options.append("--%s=%s" % (name.replace("_", "-"), value))
    config.parse_config(options)
    netsvc.init_logger()

    from odoo.addons.ab_website_sale_product.services.website_sync_worker import run_worker

    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    signal.signal(signal.SIGINT, lambda *_args: stop.set())
    run_worker(args.database, stop)


if __name__ == "__main__":
    main()
