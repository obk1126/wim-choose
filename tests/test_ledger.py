"""Ledger contract tests: confirm/recall/replay are local and never run a model."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / 'scripts'))
    spec.loader.exec_module(module)
    return module


v = load('validate')
L = load('ledger')


def case(name):
    return v.load_json(ROOT / 'examples' / name)


def row_request():
    return {
        'state': [{'id': 'a', 'name': ' Min Ha ', 'ok': False}, {'id': 'b', 'name': 'minha', 'ok': True}],
        'sources': [{'id': 's', 'kind': 'json', 'label': 'fixture', 'scope': 'both rows',
                     'complete': True, 'state_paths': [''], 'locations': {'/1/ok': 'rows.json#b.ok'}}],
        'policy': {'rules': ['Use the supplied ready boolean.']},
        'questions': [{'id': 'q', 'type': 'predicate', 'instructions': 'Is ok true?'}],
        'unit': {'mode': 'row', 'complete': True,
                 'subjects': [{'subject_id': 'a', 'pointer': '/0', 'source_ids': ['s']},
                              {'subject_id': 'b', 'pointer': '/1', 'source_ids': ['s']}]},
    }


def row_config():
    return {'policy': {'rules': ['Use the supplied ready boolean.']},
            'questions': [{'id': 'q', 'type': 'predicate', 'instructions': 'Is ok true?'}],
            'unit': {'mode': 'row', 'id_field': 'id'},
            'ledger': {'path': 'ledger.jsonl', 'keys': [{'pointer': '/name'}]}}


class LedgerTests(unittest.TestCase):
    def test_examples_24_to_26_come_from_recall(self):
        base = case('06_duplicate_names.case.json')['input']
        config = v.load_json(ROOT / 'examples/configs/people.json')
        entries = L.read_ledger(ROOT / 'examples/data/ledger.jsonl')
        recalled, stats = L.recall_request(copy.deepcopy(base), config, entries)
        self.assertEqual(recalled, case('24_ledger_match.case.json')['input'])
        self.assertEqual({'subjects': 1, 'hit_subjects': 1, 'injected': 1, 'stale': 0}, stats)
        # Same key, different policy -> stale, nothing applicable.
        changed = copy.deepcopy(base)
        changed['policy']['rules'].append('새 규칙')
        recalled, stats = L.recall_request(changed, config, entries)
        self.assertEqual(1, stats['stale'])
        self.assertTrue(recalled['state']['ledger'][0]['stale'])

    def test_key_normalization_is_explicit(self):
        req, cfg = row_request(), row_config()
        keys = cfg['ledger']['keys']
        self.assertEqual(['min ha'], L.subject_key(req['state'], req['unit']['subjects'][0], keys))
        self.assertEqual(['minha'], L.subject_key(req['state'], req['unit']['subjects'][1], keys))
        keys[0]['normalize'] = ['trim']
        self.assertEqual(['Min Ha'], L.subject_key(req['state'], req['unit']['subjects'][0], keys))
        with self.assertRaises(ValueError):
            L.subject_key(req['state'], req['unit']['subjects'][0], [{'pointer': '/ok'}])
        # alpha_prefix keeps the letters of a code; a code without letters is kept whole, never emptied.
        self.assertEqual('sale', L.normalize('SALE021', ['alpha_prefix', 'lower']))
        self.assertEqual('021', L.normalize('021', ['alpha_prefix']))

    def test_recall_wraps_rows_and_rewrites_pointers(self):
        req, cfg = row_request(), row_config()
        entry = {'ledger_id': 'L-00001', 'question_id': 'q', 'key': ['minha'], 'value': True,
                 'decided_by': 'x', 'decided_at': '2026-10-01T00:00:00+00:00',
                 'policy_hash': L.policy_hash(req, 'q')}
        new, stats = L.recall_request(req, cfg, [entry])
        self.assertEqual([], v.validate_input(new))
        self.assertEqual({'input': {'id': 'b', 'name': 'minha', 'ok': True}, 'ledger': [
            {'ledger_id': 'L-00001', 'question_id': 'q', 'value': True, 'decided_by': 'x',
             'decided_at': '2026-10-01T00:00:00+00:00', 'key': ['minha'], 'stale': False}]},
            new['state'][1])
        self.assertEqual([], new['state'][0]['ledger'])
        self.assertEqual([''], new['sources'][0]['state_paths'])
        self.assertEqual({'/1/input/ok': 'rows.json#b.ok'}, new['sources'][0]['locations'])
        self.assertEqual(['s', 'ledger'], new['unit']['subjects'][0]['source_ids'])
        self.assertEqual(['/0/ledger', '/1/ledger'], new['sources'][-1]['state_paths'])
        self.assertIn(L.LEDGER_RULE, new['policy']['rules'])
        self.assertEqual(stats['hit_subjects'], 1)
        # Policy hash ignores the injected ledger rule, so confirm after recall matches.
        self.assertEqual(L.policy_hash(req, 'q'), L.policy_hash(new, 'q'))
        # Recall is not applied twice under the same source id.
        with self.assertRaises(ValueError):
            L.recall_request(new, cfg, [entry])

    def test_ledger_match_output_guards(self):
        req = case('24_ledger_match.case.json')['input']
        out = case('24_ledger_match.case.json')['expected']
        self.assertEqual([], v.validate_output(out, req))
        bad = copy.deepcopy(out)
        bad['results'][0]['value'] = 'p2'
        self.assertIn('LEDGER_MATCH value differs from the ledger', ' '.join(v.validate_output(bad, req)))
        bad = copy.deepcopy(out)
        bad['results'][0]['evidence'] = [bad['results'][0]['evidence'][1]]
        self.assertIn('requires evidence from a ledger source', ' '.join(v.validate_output(bad, req)))
        stale = case('26_ledger_stale.case.json')['input']
        self.assertIn('requires an applicable ledger entry', ' '.join(v.validate_output(out, stale)))
        # Without recall there is no ledger at all.
        plain = case('06_duplicate_names.case.json')['input']
        plain_out = copy.deepcopy(out)
        plain_out['results'][0]['evidence'] = [{'source_id': 's1', 'location': '/requested_name', 'fact': '민하'}]
        self.assertTrue(v.validate_output(plain_out, plain))

    def test_confirm_appends_and_replay_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            req, cfg = row_request(), row_config()
            (d / 'req.json').write_text(json.dumps(req), encoding='utf-8')
            (d / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
            script = str(ROOT / 'scripts/ledger.py')
            run = lambda *a: subprocess.run([sys.executable, script, *a], text=True, capture_output=True, check=False)
            ok = run('confirm', '--request', str(d / 'req.json'), '--config', str(d / 'config.json'),
                     '--subject', 'a', '--question', 'q', '--value', 'true', '--by', 'tester',
                     '--at', '2026-10-01T00:00:00+00:00')
            self.assertEqual(0, ok.returncode, ok.stderr)
            entry = json.loads(ok.stdout)
            self.assertEqual(['min ha'], entry['key'])
            self.assertIs(True, entry['value'])
            self.assertEqual(1, len(L.read_ledger(d / 'ledger.jsonl')))
            # A value outside the question contract is refused and not written.
            bad = run('confirm', '--request', str(d / 'req.json'), '--config', str(d / 'config.json'),
                      '--subject', 'a', '--question', 'q', '--value', '"yes"', '--by', 'tester')
            self.assertEqual(2, bad.returncode)
            self.assertEqual(1, len(L.read_ledger(d / 'ledger.jsonl')))
            rec = run('recall', '--request', str(d / 'req.json'), '--config', str(d / 'config.json'),
                      '--out', str(d / 'recalled.json'))
            self.assertEqual(0, rec.returncode, rec.stderr)
            (d / 'reqs').mkdir()
            (d / 'reqs' / 'r.json').write_text((d / 'recalled.json').read_text(encoding='utf-8'), encoding='utf-8')
            rep = run('replay', '--requests', str(d / 'reqs'), '--config', str(d / 'config.json'))
            self.assertEqual(0, rep.returncode, rep.stderr)
            report = json.loads(rep.stdout)
            self.assertEqual(2, report['subject_questions'])
            self.assertEqual(1, report['ledger_single_hit'])


if __name__ == '__main__':
    unittest.main()
