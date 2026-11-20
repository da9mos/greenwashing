"""Offline response contract and persisted dependency guard; no provider calls."""
import json
from pathlib import Path
import re

class ProviderDependencyError(RuntimeError):
    def __init__(self, kind):
        self.kind = kind
        self.status_code = {'balance': 402, 'auth': 401, 'access': 403}.get(kind, 403)
        super().__init__('DeepSeek provider dependency: ' + kind + '; explicit operator resolution required')

def guard_provider(base):
    base = Path(base)
    job_path = base / '_проверка/job.json'
    job = json.loads(job_path.read_text()) if job_path.is_file() else {}
    status = str(job.get('status', ''))
    if status.startswith('blocked_deepseek_'):
        raise ProviderDependencyError(status.removeprefix('blocked_deepseek_'))
    control_path = base / '_проверка/deepseek_controller.json'
    control = json.loads(control_path.read_text()) if control_path.is_file() else {}
    dependency = control.get('dependency') or {}
    if dependency.get('state') == 'deferred_external_dependency':
        raise ProviderDependencyError(dependency.get('kind', 'access'))

def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate response JSON key: ' + key)
        obj[key] = value
    return obj

def reject_constant(value):
    raise ValueError('Non-finite JSON constant: ' + value)

def decode_answer(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)

def validate_answer(answer, pdf_page):
    if not isinstance(answer, dict):
        raise ValueError('Page response must be an object')
    if type(answer.get('pdf_page')) is not int or answer['pdf_page'] != pdf_page:
        raise ValueError('Page response identity mismatch')
    if not isinstance(answer.get('markdown'), str):
        raise ValueError('Page markdown must be a string')
    issues = answer.get('issues')
    if not isinstance(issues, list) or any(not isinstance(x, str) or not x.strip() for x in issues):
        raise ValueError('Page issues must contain only nonempty strings')
    markers = re.findall(r'<!--\s*pdf_page\s*:\s*(\d+)\s*-->', answer['markdown'])
    if any(int(n) != pdf_page for n in markers):
        raise ValueError('Page response must not inject another page identity')
    if re.search(r'<\s*(?:script|iframe|object|embed)\b|<[^>]*\bon\w+\s*=|<[^>]*(?:href|src)\s*=\s*[\"\']?\s*javascript:', answer['markdown'], re.I):
        raise ValueError('Active HTML must be escaped as source text')
    return answer
