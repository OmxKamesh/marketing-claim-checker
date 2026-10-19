#!/usr/bin/env python3
"""Deterministic local claim ledger. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import re
import html


class Invalid(ValueError):
    pass


def local_file(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise Invalid('source path must be a nonempty relative path')
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise Invalid('source path escapes evidence root')
    return target


def read_source(root, spec):
    path = local_file(root, spec['path'])
    if 'sha256' in spec and (not isinstance(spec['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', spec['sha256'])):
        raise Invalid('source sha256 must be 64 lowercase hex digits')
    start, end = spec.get('start'), spec.get('end')
    if type(start) is not int or type(end) is not int or not 1 <= start <= end:
        raise Invalid('start/end must be positive ordered line numbers')
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise Invalid('source exceeds 2 MB limit')
    digest = hashlib.sha256(raw).hexdigest()
    if 'sha256' in spec and spec['sha256'] != digest:
        return None, {'path': spec['path'], 'sha256': digest}, 'source hash changed'
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    info = {'path': spec['path'], 'start': start, 'end': end, 'sha256': digest}
    if end > len(lines):
        return None, info, 'source line range unavailable'
    return '\n'.join(lines[start - 1:end]), info, None


def evaluate_check(root, check, excerpts=False):
    if not isinstance(check, dict) or check.get('kind') != 'exact-lines':
        raise Invalid('supported check kind: exact-lines')
    if not isinstance(check.get('expected'), str):
        raise Invalid('expected must be a string')
    source = check.get('source')
    if not isinstance(source, dict) or 'path' not in source:
        raise Invalid('check requires source')
    # Validate containment even for unavailable files.
    local_file(root, source['path'])
    try:
        actual, info, problem = read_source(root, source)
    except (OSError, UnicodeError):
        return {'status': 'unknown', 'reason': 'source missing, unreadable, or not UTF-8',
                'source': {'path': source['path']}}
    if problem:
        return {'status': 'unknown', 'reason': problem, 'source': info}
    result = {'status': 'verified' if actual == check['expected'] else 'contradicted',
              'reason': 'literal lines match' if actual == check['expected'] else 'literal lines differ',
              'source': info}
    if excerpts:
        result.update(actual=actual, expected=check['expected'])
    return result


def ledger(root, manifest, excerpts=False):
    root = Path(root).resolve()
    if isinstance(manifest, dict) and manifest.get('version') == 2:
        return observation_ledger(root, manifest)
    if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('claims'), list) or not manifest['claims']:
        raise Invalid('expected version 1 and a nonempty claims array')
    ids, results = set(), []
    for claim in manifest['claims']:
        if not isinstance(claim, dict) or not isinstance(claim.get('id'), str) or not claim['id'] or claim['id'] in ids:
            raise Invalid('claim IDs must be nonempty unique strings')
        ids.add(claim['id'])
        for key in ('claim', 'scope'):
            if not isinstance(claim.get(key), str) or not claim[key].strip():
                raise Invalid('each claim requires nonempty claim and scope strings')
        checks = claim.get('checks', [])
        if not isinstance(checks, list):
            raise Invalid('checks must be an array')
        evidence = [evaluate_check(root, c, excerpts) for c in checks]
        statuses = {e['status'] for e in evidence}
        status = ('contradicted' if 'contradicted' in statuses else
                  'unknown' if not evidence or 'unknown' in statuses else 'verified')
        results.append({'id': claim['id'], 'claim': claim['claim'], 'scope': claim['scope'],
                        'status': status, 'evidence': evidence})
    counts = {s: sum(c['status'] == s for c in results) for s in ('verified', 'contradicted', 'unknown')}
    return {'version': 1, 'method': 'literal local evidence assertions; not semantic or runtime verification',
            'counts': counts, 'claims': results}


def nonempty(obj, key):
    if not isinstance(obj.get(key), str) or not obj[key].strip():
        raise Invalid(f'{key} must be a nonempty string')
    return obj[key]


def instant(value):
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if d.tzinfo is None:
            raise ValueError()
        return d.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise Invalid('timestamps must be ISO 8601 with timezone')


def observation_ledger(root, manifest, now=None):
    now = now or datetime.now(timezone.utc)
    claims, evidence = manifest.get('claims'), manifest.get('evidence')
    if not isinstance(claims, list) or not claims or not isinstance(evidence, list):
        raise Invalid('version 2 requires nonempty claims and an evidence array')
    known = {}
    for c in claims:
        if not isinstance(c, dict):
            raise Invalid('claim must be an object')
        cid = nonempty(c, 'id')
        if cid in known:
            raise Invalid('duplicate claim ID')
        for key in ('exact_text', 'scope'):
            nonempty(c, key)
        checks = c.get('required_checks')
        if not isinstance(checks, list) or any(not isinstance(k, str) or not k for k in checks) or len(checks) != len(set(checks)):
            raise Invalid('required_checks must be unique nonempty strings')
        source = c.get('source')
        if not isinstance(source, dict) or 'path' not in source:
            raise Invalid('claim source required')
        # Source contains original claim text, not just an arbitrary location.
        try:
            actual, source_info, issue = read_source(root, source)
        except (OSError, UnicodeError):
            actual, source_info, issue = None, source, 'claim source unavailable'
        if actual is not None and actual != c['exact_text']:
            issue = 'claim source no longer matches exact_text'
        known[cid] = (c, source_info, issue)
    seen, by_claim = set(), {cid: {} for cid in known}
    for e in evidence:
        if not isinstance(e, dict):
            raise Invalid('evidence must be an object')
        eid = nonempty(e, 'id')
        if eid in seen:
            raise Invalid('duplicate evidence ID')
        seen.add(eid)
        cid, check = nonempty(e, 'claim_id'), nonempty(e, 'check_id')
        if cid not in known or check not in known[cid][0]['required_checks']:
            raise Invalid('evidence references unknown claim/check')
        if check in by_claim[cid]:
            raise Invalid('multiple observations for same claim/check; select one current observation')
        for key in ('scope', 'method'):
            nonempty(e, key)
        observed = instant(e.get('time'))
        if observed > now:
            raise Invalid('evidence timestamp is in the future')
        expires = instant(e.get('valid_until'))
        if expires < observed:
            raise Invalid('valid_until predates observation')
        if e.get('result') not in ('pass', 'fail', 'blocked'):
            raise Invalid('result must be pass, fail or blocked')
        artifact = e.get('artifact')
        if not isinstance(artifact, dict) or not isinstance(artifact.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', artifact['sha256']):
            raise Invalid('artifact requires lowercase SHA-256 and relative path')
        path = local_file(root, artifact.get('path'))
        status, reason = e['result'], 'recorded observation'
        try:
            with path.open('rb') as f:
                digest = hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(f.read()).hexdigest()
            if digest != artifact['sha256']:
                status, reason = 'stale', 'artifact hash changed'
        except OSError:
            status, reason = 'unknown', 'artifact unavailable'
        if expires < now:
            status, reason = 'stale', 'observation expired'
        if e['scope'] != known[cid][0]['scope']:
            status, reason = 'unknown', 'observation scope does not exactly match claim scope'
        by_claim[cid][check] = {'id': eid, 'check_id': check, 'status': status, 'reason': reason,
                               'method': e['method'], 'time': e['time'], 'valid_until': e['valid_until'],
                               'source': artifact}
    results = []
    for cid, (c, source, issue) in known.items():
        items = [by_claim[cid].get(k, {'check_id': k, 'status': 'unknown', 'reason': 'required observation missing', 'source': {'path': '(none)'}}) for k in c['required_checks']]
        states = {i['status'] for i in items}
        status = ('unknown' if issue else 'contradicted' if 'fail' in states else
                  'supported-in-tested-scope' if items and states == {'pass'} else 'unknown')
        results.append({'id': cid, 'claim': c['exact_text'], 'scope': c['scope'], 'source': source,
                        'source_issue': issue, 'status': status, 'evidence': items})
    counts = {s: sum(c['status'] == s for c in results) for s in ('supported-in-tested-scope', 'contradicted', 'unknown')}
    return {'version': 2, 'method': 'supplied observations, validated references and artifact hashes; observations not independently rerun', 'counts': counts, 'claims': results}


def safe_markdown(value):
    """Render supplied values as inert text, never report markup or HTML."""
    value = html.escape(str(value), quote=True)
    value = value.replace('\r', ' ').replace('\n', ' ')
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def markdown(report):
    esc = safe_markdown
    lines = ['# Promise Check', '', esc(report['method']), '',
             ', '.join(f'{v} {k}' for k, v in report['counts'].items()), '']
    for c in report['claims']:
        lines.extend([f"## {esc(c['id'])}: {esc(c['status'])}", '', esc(c['claim']), '', f"Scope: {esc(c['scope'])}", ''])
        if c.get('source'):
            s = c['source']
            lines.append(f"Claim source: {esc(s['path'])}:{esc(s.get('start', '?'))}-{esc(s.get('end', '?'))}; SHA-256 {esc(s.get('sha256', 'unavailable'))}")
        if c.get('source_issue'):
            lines.append(f"- Claim source: {esc(c['source_issue'])}")
        if not c['evidence']:
            lines.append('- No evidence checks supplied; unknown.')
        for e in c['evidence']:
            s = e['source']
            loc = s['path'] + (f":{s['start']}-{s['end']}" if 'start' in s else '')
            lines.append(f"- {esc(e['status'])}: {esc(loc)} — {esc(e['reason'])}; SHA-256 {esc(s.get('sha256', 'unavailable'))}")
        lines.append('')
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--format', choices=['json', 'markdown'], default='markdown')
    p.add_argument('--output', type=Path, help='Write to a new file; refuses to overwrite')
    p.add_argument('--include-excerpts', action='store_true', help='Include actual/expected text in JSON; inspect for secrets before sharing')
    a = p.parse_args(argv)
    try:
        report = ledger(a.root, json.loads(a.manifest.read_text(encoding='utf-8-sig')), a.include_excerpts)
    except (Invalid, OSError, UnicodeError, json.JSONDecodeError, KeyError) as e:
        print(f'Invalid input: {e}', file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, ensure_ascii=True) if a.format == 'json' else markdown(report)
    if a.output:
        try:
            with a.output.open('x', encoding='utf-8') as f:
                f.write(rendered + '\n')
        except OSError as e:
            print(f'Cannot create output: {e}', file=sys.stderr)
            return 2
    else:
        print(rendered)
    return 1 if report['counts']['contradicted'] or report['counts']['unknown'] else 0


if __name__ == '__main__':
    sys.exit(main())
