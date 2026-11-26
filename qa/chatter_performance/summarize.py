import argparse
import json
import math
from pathlib import Path


def summarize(path):
    document = json.loads(path.read_text())
    stages = {}
    for sample in document['samples']:
        stage = stages.setdefault(sample['stage'], {'durations': [], 'errors': 0})
        stage['errors'] += int(bool(sample['error']))
        if not sample['error']:
            duration = float(sample['duration_ms'])
            if not math.isfinite(duration) or duration < 0:
                raise ValueError('Invalid sample duration')
            stage['durations'].append(duration)
    metrics = {}
    for name, stage in stages.items():
        values = sorted(stage['durations'])
        metrics[name] = {'samples': len(values), 'errors': stage['errors']}
        for percentile in (50, 95, 99):
            metrics[name]['p' + str(percentile) + '_ms'] = (
                round(values[math.ceil(len(values) * percentile / 100) - 1], 3) if values else None)
    return {'fixture': document['fixture'], 'metrics': metrics,
            'resource': document['resource'], 'queue_growth': document['queue_growth'],
            'sender_to_receiver': document['sender_to_receiver']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    arguments = parser.parse_args()
    result = {'before': summarize(arguments.before), 'after': summarize(arguments.after),
              'staging_capacity': 'Deferred by user; not certified',
              'sustainable_messages_per_second': None,
              'percentile_method': 'Nearest rank; 30 sequential samples per endpoint'}
    arguments.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
