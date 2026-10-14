"""Contract and failure-path tests; no model inference is performed."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wim_validate', ROOT / 'scripts/validate.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def request():
    return {
        'state': [{'id': 'a', 'ready': False, 'amount': 0},
                  {'id': 'b', 'ready': True, 'amount': None}],
        'sources': [{'id': 's', 'kind': 'json', 'label': 'fixture',
                     'scope': 'Both provided rows', 'complete': True,
                     'state_paths': ['']}],
        'policy': {'rules': ['Use the supplied ready boolean.']},
        'questions': [{'id': 'q', 'type': 'predicate', 'instructions': 'Is ready true?'}],
        'unit': {'mode': 'row', 'complete': True,
                 'subjects': [{'subject_id': 'a', 'pointer': '/0', 'source_ids': ['s']},
                              {'subject_id': 'b', 'pointer': '/1', 'source_ids': ['s']}]},
    }


def output():
    return {'results': [
        {'subject_id': sid, 'id': 'q', 'type': 'predicate', 'status': 'decided',
         'value': value, 'reason_code': reason,
         'evidence': [{'source_id': 's', 'location': f'/{index}/ready', 'fact': fact}],
         'review_required': False}
        for index, sid, value, reason, fact in [
            (0, 'a', False, 'CONDITION_FALSE', 'false'),
            (1, 'b', True, 'CONDITION_TRUE', 'true')]]}


def review(row, code='MISSING_INFORMATION'):
    row.update(status='needs_review', value=None, reason_code=code,
               evidence=[], review_required=True)


class ValidationTests(unittest.TestCase):
    def test_schemas_are_valid_draft202012(self):
        for name in ('input', 'output', 'config'):
            Draft202012Validator.check_schema(v.load_json(ROOT / 'schemas' / f'{name}.schema.json'))

    def test_false_is_decided_not_null(self):
        self.assertEqual([], v.validate_input(request()))
        self.assertEqual([], v.validate_output(output(), request()))

    def test_bool_is_not_numeric_score(self):
        row = output()['results'][0]
        row.update(type='score', value=False, reason_code='RUBRIC_MATCH')
        self.assertTrue(v.validate_output({'results': [row]}))

    def test_zero_score_is_valid(self):
        req, out = request(), output()
        req['questions'] = [{'id': 'q', 'type': 'score', 'instructions': 'Use amount score.',
                             'rubric': [{'score': 0, 'criteria': 'amount is zero'},
                                        {'score': 1, 'criteria': 'amount is one'}]}]
        for row in out['results']:
            row['type'] = 'score'
        out['results'][0].update(value=0, reason_code='RUBRIC_MATCH',
                                evidence=[{'source_id': 's', 'location': '/0/amount', 'fact': '0'}])
        review(out['results'][1])
        self.assertEqual([], v.validate_output(out, req))
        out['results'][0]['value'] = 0.5
        self.assertTrue(v.validate_output(out, req))

    def test_null_false_and_zero_evidence_are_distinct(self):
        req, out = request(), output()
        out['results'][0]['evidence'] = [{'source_id': 's', 'location': '/0/amount', 'fact': '0'}]
        self.assertEqual([], v.validate_output(out, req))
        out['results'][0]['evidence'][0]['fact'] = 'false'
        self.assertTrue(v.validate_output(out, req))
        review(out['results'][1])
        out['results'][0]['evidence'][0]['fact'] = '0'
        out['results'][1]['evidence'] = [{'source_id': 's', 'location': '/1/amount', 'fact': 'null'}]
        self.assertEqual([], v.validate_output(out, req))

    def test_empty_fact_only_matches_empty_cell(self):
        req, out = request(), output()
        req['state'][0]['note'] = ''
        out['results'][0]['evidence'] = [{'source_id': 's', 'location': '/0/note', 'fact': ''}]
        self.assertEqual([], v.validate_output(out, req))
        req['state'][0]['note'] = 'nonempty'
        self.assertTrue(v.validate_output(out, req))

    def test_forged_evidence_rejected(self):
        out = output()
        out['results'][0]['evidence'][0]['fact'] = 'The source says false.'
        self.assertTrue(v.validate_output(out, request()))

    def test_substring_quote_allowed_but_not_semantic_claim(self):
        req, out = request(), output()
        req['state'][0]['note'] = 'We received your request.'
        out['results'][0]['evidence'] = [{'source_id': 's', 'location': '/0/note', 'fact': 'received'}]
        self.assertEqual([], v.validate_output(out, req))

    def test_wrong_row_evidence_rejected(self):
        out = output()
        out['results'][0]['evidence'][0].update(location='/1/ready', fact='true')
        self.assertTrue(v.validate_output(out, request()))

    def test_wrong_source_evidence_rejected(self):
        req, out = request(), output()
        req['sources'].append({'id': 'second', 'kind': 'json', 'label': 'second',
                               'scope': 'Only row b', 'complete': True, 'state_paths': ['/1']})
        out['results'][0]['evidence'][0]['source_id'] = 'second'
        self.assertTrue(v.validate_output(out, req))

    def test_evidence_must_be_in_source_even_if_in_subject(self):
        req, out = request(), output()
        req['sources'][0]['state_paths'] = ['/0/id', '/1/id']
        self.assertEqual([], v.validate_input(req))
        self.assertTrue(v.validate_output(out, req))

    def test_source_covering_no_subject_data_rejected(self):
        req = request()
        req['sources'][0]['state_paths'] = ['/1']
        self.assertTrue(v.validate_input(req))

    def test_object_evidence_not_supported(self):
        out = output()
        out['results'][0]['evidence'][0].update(location='/0', fact='{"ready":false}')
        self.assertTrue(v.validate_output(out, request()))

    def test_missing_duplicate_and_unknown_results_rejected(self):
        for operation in ('missing', 'duplicate', 'unknown'):
            with self.subTest(operation=operation):
                out = output()
                if operation == 'missing':
                    out['results'].pop()
                elif operation == 'duplicate':
                    out['results'].append(copy.deepcopy(out['results'][0]))
                else:
                    out['results'][0]['subject_id'] = 'unknown'
                self.assertTrue(v.validate_output(out, request()))

    def test_unknown_choice_rejected(self):
        req, out = request(), output()
        req['questions'] = [{'id': 'q', 'type': 'choice', 'instructions': 'Choose.',
                             'choices': [{'value': 'x', 'meaning': 'x'}]}]
        for row in out['results']:
            row.update(type='choice', reason_code='CHOICE_MATCH', value='not-listed')
        self.assertTrue(v.validate_output(out, req))

    def test_duplicate_ids_choices_and_scores_rejected(self):
        for field in ('question', 'subject', 'source', 'choice', 'score'):
            req = request()
            if field == 'question':
                req['questions'].append(copy.deepcopy(req['questions'][0]))
            elif field == 'subject':
                req['unit']['subjects'][1]['subject_id'] = 'a'
            elif field == 'source':
                req['sources'].append(copy.deepcopy(req['sources'][0]))
            elif field == 'choice':
                req['questions'] = [{'id': 'q', 'type': 'choice', 'instructions': 'x',
                                     'choices': [{'value': 'x', 'meaning': 'one'},
                                                 {'value': 'x', 'meaning': 'two'}]}]
            else:
                req['questions'] = [{'id': 'q', 'type': 'score', 'instructions': 'x',
                                     'rubric': [{'score': 0, 'criteria': 'one'},
                                                {'score': 0.0, 'criteria': 'two'}]}]
            with self.subTest(field=field):
                self.assertTrue(v.validate_input(req))

    def test_overlap_row_subjects_rejected(self):
        req = request()
        req['unit']['subjects'][0]['pointer'] = ''
        self.assertTrue(v.validate_input(req))

    def test_source_locations_must_resolve_in_source(self):
        req = request()
        req['sources'][0]['locations'] = {'/missing': 'row 99'}
        self.assertTrue(v.validate_input(req))

    def test_missing_required_field_rejects_entire_request(self):
        req = request()
        del req['policy']
        self.assertTrue(v.validate_input(req))
        self.assertEqual([], v.validate_output(v.invalid_result('MISSING_REQUIRED_FIELD'), req))
        self.assertTrue(v.validate_output(output(), req))

    def test_invalid_sentinel_shape_and_valid_request_sentinel_rejected(self):
        sentinel = v.invalid_result()
        self.assertEqual([], v.validate_output(sentinel, {}))
        self.assertTrue(v.validate_output(sentinel, request()))
        sentinel['results'][0]['id'] = 'q'
        self.assertTrue(v.validate_output(sentinel, {}))
        self.assertTrue(v.validate_output(sentinel))

    def test_whole_decision_requires_known_complete_scope(self):
        req, out = request(), output()
        req['unit'].update(mode='whole', subjects=[{'subject_id': 'a', 'pointer': '', 'source_ids': ['s']}])
        out['results'] = out['results'][:1]
        self.assertEqual([], v.validate_output(out, req))
        for field, value in [('unit', False), ('unit', None), ('source', False), ('source', None)]:
            modified = copy.deepcopy(req)
            if field == 'unit':
                modified['unit']['complete'] = value
            else:
                modified['sources'][0]['complete'] = value
            self.assertTrue(v.validate_output(out, modified))
            held = copy.deepcopy(out)
            review(held['results'][0], 'INCOMPLETE_SCOPE')
            self.assertEqual([], v.validate_output(held, modified))

    def test_whole_pointer_must_be_root(self):
        req = request()
        req['unit'].update(mode='whole', subjects=req['unit']['subjects'][:1])
        self.assertTrue(v.validate_input(req))

    def test_omitted_targets_are_explicit_review_results(self):
        req, out = request(), output()
        req['unit']['omitted_subject_ids'] = ['b']
        self.assertTrue(v.validate_output(out, req))
        review(out['results'][1], 'NOT_PROCESSED')
        self.assertEqual([], v.validate_output(out, req))
        req['unit']['omitted_subject_ids'] = []
        self.assertTrue(v.validate_output(out, req))
        req['unit']['omitted_subject_ids'] = ['unknown']
        self.assertTrue(v.validate_input(req))

    def test_decided_requires_evidence_and_consistent_reason(self):
        out = output()
        out['results'][0]['evidence'] = []
        self.assertTrue(v.validate_output(out, request()))
        out = output()
        out['results'][0]['reason_code'] = 'CONDITION_TRUE'
        self.assertTrue(v.validate_output(out, request()))
        out = output()
        out['results'][0]['reason_code'] = 'POLICY_BLOCKED'
        self.assertEqual([], v.validate_output(out, request()))
        out['results'][1]['reason_code'] = 'POLICY_BLOCKED'
        self.assertTrue(v.validate_output(out, request()))

    def test_absence_uses_checked_scope_not_unrelated_quote(self):
        req = request()
        req['questions'] = [{'id': 'q', 'type': 'predicate', 'instructions': 'Is a phone listed?'}]
        out = output()
        absent = {'source_id': 's', 'location': '/0', 'fact': '', 'kind': 'checked_scope'}
        out['results'][0].update(reason_code='CONDITION_ABSENT', evidence=[absent])
        self.assertEqual([], v.validate_output(out, req))
        # An unrelated quote cannot carry an absence decision.
        bad = copy.deepcopy(out)
        bad['results'][0]['evidence'] = [{'source_id': 's', 'location': '/0/id', 'fact': 'a'}]
        self.assertTrue(v.validate_output(bad, req))
        # checked_scope is reserved for CONDITION_ABSENT.
        bad = copy.deepcopy(out)
        bad['results'][0]['reason_code'] = 'CONDITION_FALSE'
        self.assertTrue(v.validate_output(bad, req))
        # checked_scope carries no quote.
        bad = copy.deepcopy(out)
        bad['results'][0]['evidence'][0]['fact'] = 'a'
        self.assertTrue(v.validate_output(bad, req))
        # A decided absence still names the checked range.
        bad = copy.deepcopy(out)
        bad['results'][0]['evidence'] = []
        self.assertTrue(v.validate_output(bad, req))
        # Only predicate false.
        bad = copy.deepcopy(out)
        bad['results'][0]['value'] = True
        self.assertTrue(v.validate_output(bad, req))
        # Checked range must stay inside the subject.
        bad = copy.deepcopy(out)
        bad['results'][0]['evidence'][0]['location'] = '/1'
        self.assertTrue(v.validate_output(bad, req))

    def test_absence_requires_complete_sources(self):
        req = request()
        req['sources'][0]['complete'] = None
        out = output()
        out['results'][0].update(reason_code='CONDITION_ABSENT', evidence=[
            {'source_id': 's', 'location': '/0', 'fact': '', 'kind': 'checked_scope'}])
        self.assertTrue(v.validate_output(out, req))
        req['sources'][0]['complete'] = True
        self.assertEqual([], v.validate_output(out, req))

    def test_request_sentinel_type_is_reserved_both_ways(self):
        sentinel = v.invalid_result()
        self.assertEqual('request', sentinel['results'][0]['type'])
        self.assertEqual([], v.validate_output(sentinel, {}))
        # A question result may not borrow the envelope type.
        out = output()
        out['results'][0]['type'] = 'request'
        self.assertTrue(v.validate_output(out, request()))
        # The reserved ID may not carry a question type.
        bad = copy.deepcopy(sentinel)
        bad['results'][0]['type'] = 'choice'
        self.assertTrue(v.validate_output(bad, {}))
        self.assertTrue(v.validate_output(bad))

    def test_explain_uses_longest_recorded_prefix(self):
        req = request()
        req['sources'][0]['locations'] = {'': 'rows.json', '/0': 'rows.json#record-a'}
        rows = v.explain_evidence(output(), req)
        self.assertEqual('rows.json#record-a /ready', rows[0]['source_location'])
        self.assertEqual('rows.json /1/ready', rows[1]['source_location'])
        del req['sources'][0]['locations']
        self.assertIsNone(v.explain_evidence(output(), req)[0]['source_location'])

    def test_review_and_invalid_require_null_true(self):
        for status, reason in [('needs_review', 'MISSING_INFORMATION'), ('invalid_input', 'INVALID_SCOPE')]:
            out = output()
            out['results'][0].update(status=status, reason_code=reason)
            self.assertTrue(v.validate_output(out, request()))
            out['results'][0].update(value=None, review_required=True)
            self.assertEqual([], v.validate_output(out, request()))

    def test_pointer_escape_and_bad_array_index(self):
        state = {'a/b': {'~x': [False]}}
        self.assertIs(False, v.resolve_pointer(state, '/a~1b/~0x/0'))
        for pointer in ('/a~2b', '/a~1b/~0x/00', '/a~1b/~0x/-', '#/a~1b'):
            with self.assertRaises(ValueError):
                v.resolve_pointer(state, pointer)

    def test_json_loader_rejects_duplicates_nan_and_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for text in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}', '[NaN]', '[Infinity]', '[1e999]'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    v.load_json(path)

    def test_direct_api_rejects_nonfinite_values(self):
        for value in (float('nan'), float('inf')):
            req = request()
            req['state'][0]['amount'] = value
            self.assertTrue(v.validate_input(req))

    def test_customer_config_mapping_validation(self):
        config = {'policy': request()['policy'], 'questions': request()['questions'],
                  'unit': {'mode': 'row', 'id_field': 'id'},
                  'columns': [{'source': 'READY', 'field': 'ready', 'type': 'boolean',
                               'empty': 'preserve', 'true_values': ['yes'], 'false_values': ['no']}]}
        self.assertEqual([], v.validate_config(config))
        config['columns'][0]['false_values'] = ['yes']
        self.assertTrue(v.validate_config(config))
        config['columns'][0]['false_values'] = ['no']
        config['columns'][0]['null_tokens'] = ['']
        self.assertTrue(v.validate_config(config))

    def test_config_duplicate_fields_and_missing_date_format(self):
        config = {'policy': request()['policy'], 'questions': request()['questions'],
                  'unit': {'mode': 'single'},
                  'columns': [{'source': 'DATE', 'field': 'date', 'type': 'date', 'empty': 'null'}]}
        self.assertTrue(v.validate_config(config))
        config['columns'][0]['date_format'] = '%Y-%m-%d'
        self.assertEqual([], v.validate_config(config))
        config['columns'].append(copy.deepcopy(config['columns'][0]))
        self.assertTrue(v.validate_config(config))

    def test_extra_output_fields_rejected(self):
        out = output()
        out['results'][0]['confidence'] = 0.97
        self.assertTrue(v.validate_output(out, request()))

    def test_group_requires_grouping_keys(self):
        req = request()
        req['unit']['mode'] = 'group'
        self.assertTrue(v.validate_input(req))
        req['unit']['group_by'] = ['id']
        self.assertEqual([], v.validate_input(req))

    def test_unknown_join_source_rejected(self):
        req = request()
        req['unit']['joins'] = [{'left_source_id': 's', 'right_source_id': 'missing',
                                'left_key': 'id', 'right_key': 'id', 'relationship': 'one_to_one'}]
        self.assertTrue(v.validate_input(req))

    def test_cli_returns_json_and_failure_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for content, expected in [(request(), 0), ({}, 1)]:
                path.write_text(json.dumps(content))
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate.py'), 'input', str(path)],
                                        text=True, capture_output=True, check=False)
                self.assertEqual(expected, result.returncode)
                self.assertEqual(expected == 0, json.loads(result.stdout)['valid'])

    def test_cli_null_request_requires_rejection_sentinel(self):
        with tempfile.TemporaryDirectory() as directory:
            request_path = Path(directory) / 'request.json'
            output_path = Path(directory) / 'output.json'
            request_path.write_text('null')
            for content, expected in [(output(), 1), (v.invalid_result(), 0)]:
                output_path.write_text(json.dumps(content))
                result = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/validate.py'), 'output',
                     str(output_path), '--input', str(request_path)],
                    text=True, capture_output=True, check=False)
                self.assertEqual(expected, result.returncode)
                self.assertEqual(expected == 0, json.loads(result.stdout)['valid'])


if __name__ == '__main__':
    unittest.main()
