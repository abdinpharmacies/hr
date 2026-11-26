import argparse
import json
import math
from pathlib import Path
import re


def percentiles(values):
    values = sorted(values)
    return {'samples': len(values), **{f'p{p}': round(values[math.ceil(len(values) * p / 100) - 1], 3)
        for p in (50, 95, 99)}} if values else {'samples': 0}


def rows(directory, pattern):
    return [row for path in sorted(directory.glob(pattern)) for row in json.loads(path.read_text())['samples']]


def trace_events(directory, stage):
    exported = directory / 'trace-events.json'
    if exported.exists():
        return json.loads(exported.read_text()).get(stage, {})
    result = {}
    pattern = rf'stage={re.escape(stage)} correlation_id=(\w+) timestamp_ns=(\d+)'
    for path in directory.glob('e2e-*.log'):
        for correlation, timestamp in re.findall(pattern, path.read_text()):
            result.setdefault(correlation, []).append(int(timestamp) / 1e6)
    return result


def browser_summary(directory, filename):
    path = directory / filename
    if not path.exists():
        return {'state': 'not_recorded'}
    data = json.loads(path.read_text())
    commits = trace_events(directory, 'odoo_commit')
    stages = {name: [] for name in ('reception_to_render_ms', 'durable_ack_to_render_ms',
        'commit_to_render_ms', 'notification_to_render_ms', 'queued_ui_ack_ms')}
    for sample in data['samples']:
        for agent in sample['agents']:
            rendered = [event['timestamp_ms'] for event in agent if event['stage'] == 'rendered']
            if not rendered:
                continue
            rendered = min(rendered)
            stages['reception_to_render_ms'].append(rendered - sample['reception_ms'])
            stages['durable_ack_to_render_ms'].append(rendered - sample['durable_ack_ms'])
            committed = [at for at in commits.get(sample['correlation_id'], []) if at >= sample['reception_ms']]
            if committed:
                stages['commit_to_render_ms'].append(rendered - min(committed))
            notified = [event['timestamp_ms'] for event in agent if event['stage'] == 'browser_notification']
            if notified:
                stages['notification_to_render_ms'].append(rendered - min(notified))
    for reply in data.get('replies', []):
        stages['queued_ui_ack_ms'].append(reply['queued_ack_ms'] - reply['submission_ms'])
    return {'state': data.get('state', 'completed'), 'agents': data['agents'],
        'inbound_messages': len(data['samples']), 'replies': len(data.get('replies', [])),
        'console_errors': data.get('console_errors', []),
        **{name: percentiles(values) for name, values in stages.items()}}


def summarize(directory):
    result = {'api': {}, 'active_history': {}, 'browser': {}}
    for scale in (60, 1000):
        for phase in ('before', 'after'):
            samples = rows(directory, f'{phase}-{scale}-*.json')
            if phase == 'after':
                final_inbox = rows(directory, f'inbox-final-{scale}-*.json')
                if final_inbox:
                    samples = [row for row in samples if row['stage'] != 'inbox_first_page'] + final_inbox
            result['api'][f'{phase}_{scale}'] = {
                stage: {'duration_ms': percentiles([row['duration_ms'] for row in samples if row['stage'] == stage]),
                    'sql_count': percentiles([row['sql_count'] for row in samples if row['stage'] == stage])}
                for stage in sorted({row['stage'] for row in samples})}
    for phase in ('before', 'after'):
        samples = rows(directory, f'active-{phase}-*.json')
        result['active_history'][phase] = {key: percentiles([row[key] for row in samples])
            for key in ('duration_ms', 'requests', 'sql_count', 'response_bytes')}
    for name in ('browser-one-agent-final.json', 'browser-one-agent-inbound.json', 'browser-one-agent.json',
                 'browser-ten-foreground.json', 'browser-poll-recovery-blocked.json', 'browser-e2e.json'):
        result['browser'][name] = browser_summary(directory, name)
    variants = json.loads((directory / 'queue-variants.json').read_text())
    result['idle_variants'] = {str(interval): {
        'queue_wait_ms': percentiles([max(0, row['durable_to_mock_commit_ms'])
            for run in variants if run['interval_seconds'] == interval for row in run['samples']]),
        'cpu_seconds': percentiles([run['cpu_seconds'] for run in variants if run['interval_seconds'] == interval]),
        'connections': percentiles([run['database']['connections'] for run in variants if run['interval_seconds'] == interval])}
        for interval in (0.1, 0.25, 0.5, 1, 2)}
    workload = json.loads((directory / 'queue-five-minute-instrumented.json').read_text())
    result['five_minute'] = {key: workload[key] for key in ('duration_seconds', 'messages', 'remaining',
        'cpu_seconds', 'max_rss_kib', 'database', 'queue_wait_ms', 'burst_drain_seconds', 'overlapping_claims')}
    result['payloads'] = json.loads((directory / 'payloads-delayed.json').read_text())['worker_ms']
    result['regressions'] = json.loads((directory / 'regression-comparison.json').read_text())
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(summarize(args.directory), indent=2) + '\n')


if __name__ == '__main__':
    main()
