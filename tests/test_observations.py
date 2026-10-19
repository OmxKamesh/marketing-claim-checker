from test_promise_check import pc, SCRIPT
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class Observations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'claim.txt').write_text('Exports work on all plans.', encoding='utf-8')
        (self.root / 'evidence.txt').write_bytes(b'synthetic test record')
        self.now = datetime(2026, 10, 19, tzinfo=timezone.utc)
        self.m = {'version': 2, 'claims': [{'id': 'export', 'exact_text': 'Exports work on all plans.',
                  'source': {'path': 'claim.txt', 'start': 1, 'end': 1}, 'scope': 'all-plans', 'required_checks': ['pro', 'free']}],
                  'evidence': []}
        for check in ('pro', 'free'):
            self.m['evidence'].append({'id': check, 'claim_id': 'export', 'check_id': check, 'scope': 'all-plans',
                'result': 'pass', 'method': 'synthetic fixture, not a real browser observation', 'time': '2026-10-18T00:00:00Z',
                'valid_until': '2026-10-20T00:00:00Z', 'artifact': {'path': 'evidence.txt', 'sha256': hashlib.sha256(b'synthetic test record').hexdigest()}})

    def result(self):
        return pc.observation_ledger(self.root, self.m, self.now)['claims'][0]

    def test_all_required_pass(self):
        self.assertEqual(self.result()['status'], 'supported-in-tested-scope')

    def test_free_fail_cannot_support_all_plans(self):
        self.m['evidence'][1]['result'] = 'fail'
        self.assertEqual(self.result()['status'], 'contradicted')

    def test_pro_only_scope_cannot_support_all_plans(self):
        self.m['evidence'][0]['scope'] = 'pro-only'
        self.assertEqual(self.result()['status'], 'unknown')

    def test_missing_check_unknown(self):
        self.m['evidence'].pop()
        self.assertEqual(self.result()['status'], 'unknown')

    def test_blocked_retained(self):
        self.m['evidence'][1]['result'] = 'blocked'
        r = self.result()
        self.assertEqual(r['status'], 'unknown')
        self.assertEqual(r['evidence'][1]['status'], 'blocked')

    def test_stale_retained(self):
        self.m['evidence'][0]['valid_until'] = '2026-10-18T01:00:00Z'
        self.assertEqual(self.result()['evidence'][0]['status'], 'stale')

    def test_changed_artifact_unknown(self):
        (self.root / 'evidence.txt').write_text('changed')
        self.assertEqual(self.result()['status'], 'unknown')

    def test_changed_claim_unknown(self):
        (self.root / 'claim.txt').write_text('Different promise')
        self.assertEqual(self.result()['status'], 'unknown')

    def test_future_timestamp_invalid(self):
        self.m['evidence'][0]['time'] = '2026-10-20T00:00:00Z'
        with self.assertRaises(pc.Invalid): self.result()

    def test_duplicate_evidence_invalid(self):
        self.m['evidence'].append(copy.deepcopy(self.m['evidence'][0]))
        with self.assertRaises(pc.Invalid): self.result()

    def test_unknown_reference_invalid(self):
        self.m['evidence'][0]['claim_id'] = 'absent'
        with self.assertRaises(pc.Invalid): self.result()

    def test_bad_hash_invalid(self):
        self.m['evidence'][0]['artifact']['sha256'] = 'bad'
        with self.assertRaises(pc.Invalid): self.result()

    def test_artifact_path_escape_invalid(self):
        self.m['evidence'][0]['artifact']['path'] = '../elsewhere'
        with self.assertRaises(pc.Invalid): self.result()

    def test_expiry_before_observation_invalid(self):
        self.m['evidence'][0]['valid_until'] = '2026-10-17T00:00:00Z'
        with self.assertRaises(pc.Invalid): self.result()

    def test_markdown_contains_claim_provenance(self):
        report = pc.observation_ledger(self.root, self.m, self.now)
        rendered = pc.markdown(report)
        self.assertIn('claim\\.txt:1-1', rendered)
        self.assertIn(report['claims'][0]['source']['sha256'], rendered)

    def test_output_refuses_overwrite(self):
        manifest = self.root / 'claims.json'
        manifest.write_text(json.dumps(self.m))
        output = self.root / 'output.json'
        output.write_text('keep')
        r = subprocess.run([sys.executable, str(SCRIPT), str(manifest), '--output', str(output)], capture_output=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(output.read_text(), 'keep')

    def test_empty_observation_ledger_invalid(self):
        self.m['claims'] = []
        self.m['evidence'] = []
        with self.assertRaises(pc.Invalid): self.result()

    def test_markdown_untrusted_text_is_inert_json_preserved(self):
        payload = '<img src="https://bad"> ![pixel](https://bad) [click](https://bad) `code`\n# injected'
        report = pc.observation_ledger(self.root, self.m, self.now)
        claim = report['claims'][0]
        claim.update(id=payload, claim=payload, scope=payload)
        claim['source']['path'] = payload
        claim['evidence'][0]['source']['path'] = payload
        rendered = pc.markdown(report)
        self.assertNotIn('<img', rendered)
        self.assertNotIn('![pixel]', rendered)
        self.assertNotIn('[click](', rendered)
        self.assertNotIn('`code`', rendered)
        self.assertNotIn('\n# injected', rendered)
        self.assertIn('&lt;img', rendered)
        self.assertIn('\\!\\[pixel\\]\\(', rendered)
        self.assertEqual(json.loads(json.dumps(report))['claims'][0]['claim'], payload)
