import argparse
import configparser
import os
from pathlib import Path
import socket
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['before', 'after'], required=True)
    parser.add_argument('--baseline-addons', type=Path)
    parser.add_argument('--http-port', type=int, default=5069)
    parser.add_argument('--gevent-port', type=int, default=5072)
    args = parser.parse_args()
    if not args.database.startswith('callcenter_timing_') or args.http_port in (4091, 4092) or args.gevent_port in (4091, 4092):
        parser.error('Use a disposable timing database and unreserved ports')
    if args.phase == 'before' and not args.baseline_addons:
        parser.error('Before measurements require saved baseline addons with the same measurement tests')
    configuration = configparser.ConfigParser()
    configuration.read(args.config)
    if configuration['options'].get('db_name') != args.database:
        parser.error('The private configuration must select the disposable database exactly')
    for port in (args.http_port, args.gevent_port):
        with socket.socket() as probe:
            probe.bind(('0.0.0.0', port))
    args.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    common = [sys.executable, '/opt/odoo19/server/odoo-bin', '-c', str(args.config), '-d', args.database,
        '--no-http', '--stop-after-init', '--workers=0', '--max-cron-threads=0',
        f'--http-port={args.http_port}', f'--gevent-port={args.gevent_port}', '--test-enable']
    if args.baseline_addons:
        common.append(f'--addons-path={args.baseline_addons},/opt/odoo19/server/addons,{root}')
    for repeat in range(3):
        for scale in (60, 1000):
            name = f'{args.phase}-{scale}-{repeat}'
            subprocess.run(common + ['--test-tags=/ab_crm_sales_workspace:TestWorkspace.test_performance_api_measurements',
                f'--logfile={args.output / (name + ".log")}'], check=True,
                env=dict(os.environ, CHATTER_PERFORMANCE_CONVERSATIONS=str(scale),
                    CHATTER_PERFORMANCE_OUTPUT=str(args.output / (name + '.json'))))
        name = f'active-{args.phase}-{repeat}'
        subprocess.run(common + ['--test-tags=/ab_crm_sales_workspace:TestWorkspace.test_timing_active_api_measurements',
            f'--logfile={args.output / (name + ".log")}'], check=True,
            env=dict(os.environ, CHATTER_TIMING_ACTIVE_OUTPUT=str(args.output / (name + '.json'))))


if __name__ == '__main__':
    main()
