import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'promise_check.py'
spec = importlib.util.spec_from_file_location('promise_check', SCRIPT)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'facts.txt').write_bytes(b'Export: CSV\r\nTeam: 20\r\n')

    def manifest(self, expected='Export: CSV', **source):
        return {'version': 1, 'claims': [{'id': 'a', 'claim': 'Inventory line matches', 'scope': 'Local text only',
                'checks': [{'kind': 'exact-lines', 'source': {'path': 'facts.txt', 'start': 1, 'end': 1, **source}, 'expected': expected}]}]}

    def status(self, manifest):
        return pc.ledger(self.root, manifest)['claims'][0]['status']

    def test_exact_match_has_lines_hash_and_no_excerpt(self):
        result = pc.ledger(self.root, self.manifest())['claims'][0]
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['evidence'][0]['source']['start'], 1)
        self.assertEqual(result['evidence'][0]['source']['sha256'], hashlib.sha256((self.root / 'facts.txt').read_bytes()).hexdigest())
        self.assertNotIn('actual', result['evidence'][0])

    def test_mismatch_is_contradicted(self):
        self.assertEqual(self.status(self.manifest('Export: PDF')), 'contradicted')

    def test_missing_source_unknown(self):
        self.assertEqual(self.status(self.manifest(path='absent.txt')), 'unknown')

    def test_missing_range_unknown(self):
        self.assertEqual(self.status(self.manifest(start=100, end=100)), 'unknown')

    def test_stale_hash_unknown_even_if_text_matches(self):
        self.assertEqual(self.status(self.manifest(sha256='0' * 64)), 'unknown')

    def test_empty_checks_unknown(self):
        m = self.manifest()
        m['claims'][0]['checks'] = []
        self.assertEqual(self.status(m), 'unknown')

    def test_empty_claims_invalid(self):
        with self.assertRaises(pc.Invalid):
            pc.ledger(self.root, {'version': 1, 'claims': []})

    def test_traversal_rejected(self):
        with self.assertRaises(pc.Invalid):
            self.status(self.manifest(path='../outside.txt'))

    def test_absolute_rejected(self):
        with self.assertRaises(pc.Invalid):
            self.status(self.manifest(path=str(self.root / 'facts.txt')))

    def test_invalid_range_rejected(self):
        with self.assertRaises(pc.Invalid):
            self.status(self.manifest(start=True))

    def test_duplicate_ids_rejected(self):
        m = self.manifest()
        m['claims'].append(m['claims'][0])
        with self.assertRaises(pc.Invalid):
            pc.ledger(self.root, m)

    def test_excerpt_opt_in(self):
        r = pc.ledger(self.root, self.manifest(), True)
        self.assertEqual(r['claims'][0]['evidence'][0]['actual'], 'Export: CSV')

    def test_cli_exit_and_json(self):
        path = self.root / 'manifest.json'
        for expected, code, status in [('Export: CSV', 0, 'verified'), ('bad', 1, 'contradicted')]:
            path.write_text(json.dumps(self.manifest(expected)))
            r = subprocess.run([sys.executable, str(SCRIPT), str(path), '--root', str(self.root), '--format', 'json'], capture_output=True, text=True)
            self.assertEqual(r.returncode, code, r.stderr)
            self.assertEqual(json.loads(r.stdout)['claims'][0]['status'], status)
        path.write_text('{broken')
        r = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, '')

    def test_synthetic_demo(self):
        base = SCRIPT.parents[1] / 'examples'
        report = pc.ledger(base, json.loads((base / 'claims.json').read_text()))
        self.assertEqual(report['counts'], {'verified': 1, 'contradicted': 1, 'unknown': 1})


if __name__ == '__main__':
    unittest.main()
