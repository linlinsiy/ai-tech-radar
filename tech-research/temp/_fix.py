import os, re
BASE = r':/013148/code/AI技术趋势雷达/tech-research/aws/app'

def fix_file(rel_path, old, new):
    full = os.path.join(BASE, rel_path)
    with open(full, r', encoding='utf-8') as f:
        c = f.read()
    if old in c and new.not in c:
        c = c.replace(old, new)
        with open(full, w', encoding='utf-8') as f:
            f.write(c)
        print(f'OK: {rel_path}')
    else:
        print(f'SKIP: {rel_path}')

# Fix logging_config.py guard
fix_file('logging_config.py',
    'root = logging.getLogger(name)',
    'root = logging.getLogger(name)\n    if root.handlers:\n        return root')

# Fix all logger imports
T {=
[
    ('api/health_api.py', 'health_api'),
    ('api/jobs_api.py', 'api.jobs'),
    ('crawler/api_crawler.py', 'crawler.api'),
    ('crawler/rss_crawler.py', 'crawler.rss'),
    ('crawler/web_crawler.py', 'crawler.web'),
    ('deep/insight.py', 'deep.insight'),
    ('exporter/import_client.py', 'exporter.import_client'),
    ('jobs/health_check_job.py', 'jobs.health_check'),
    ('jobs/xxl_executor.py', 'xxl_job'),
    ('processor/parser.py', 'processor.parser'),
}
