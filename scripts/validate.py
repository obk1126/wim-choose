#!/usr/bin/env python3
"""Offline contract checks. These do not evaluate business judgment accuracy."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).resolve().parents[1] / 'schemas'
INVALID_REASONS = frozenset({
    'MISSING_REQUIRED_FIELD', 'INVALID_QUESTION', 'INVALID_CHOICES',
    'INVALID_RUBRIC', 'INVALID_SCOPE', 'INVALID_SOURCE', 'INVALID_FORMAT',
    'INVALID_POLICY',
})
RESERVED = '__request__'
POINTER = re.compile(r'^(?:/(?:[^~/]|~0|~1)*)*$')


def _reject_constant(value):
    raise ValueError(f'Non-finite JSON number: {value}')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_json(path):
    """Load strict JSON; duplicate keys and non-finite numbers are errors."""
    with Path(path).open(encoding='utf-8') as stream:
        data = json.load(stream, object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    errors = _json_errors(data)
    if errors:
        raise ValueError('; '.join(errors))
    return data


def _json_errors(data, path='$'):
    if data is None or type(data) in (str, bool, int):
        return []
    if type(data) is float:
        return [] if math.isfinite(data) else [f'{path}: number must be finite']
    if type(data) is list:
        return [error for i, item in enumerate(data)
                for error in _json_errors(item, f'{path}[{i}]')]
    if type(data) is dict:
        errors = []
        for key, item in data.items():
            if type(key) is not str:
                errors.append(f'{path}: object key must be a string')
            errors.extend(_json_errors(item, f'{path}.{key}'))
        return errors
    return [f'{path}: not a JSON value']


def _schema_errors(data, kind):
    errors = _json_errors(data)
    if errors:
        return errors
    schema = load_json(SCHEMA_DIR / f'{kind}.schema.json')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in sorted(validator.iter_errors(data),
                                key=lambda e: tuple(str(p) for p in e.absolute_path))]


def resolve_pointer(state, pointer):
    """Resolve an RFC 6901 pointer; no URI fragments or array append token."""
    if not isinstance(pointer, str) or POINTER.fullmatch(pointer) is None:
        raise ValueError('invalid RFC 6901 pointer')
    current = state
    if pointer == '':
        return current
    for encoded in pointer[1:].split('/'):
        token = encoded.replace('~1', '/').replace('~0', '~')
        if isinstance(current, dict):
            if token not in current:
                raise ValueError('pointer does not resolve')
            current = current[token]
        elif isinstance(current, list):
            if re.fullmatch(r'0|[1-9][0-9]*', token) is None:
                raise ValueError('invalid array index')
            index = int(token)
            if index >= len(current):
                raise ValueError('array index out of range')
            current = current[index]
        else:
            raise ValueError('pointer traverses a scalar')
    return current


def _within(pointer, parent):
    return parent == '' or pointer == parent or pointer.startswith(parent + '/')


def _overlap(left, right):
    return _within(left, right) or _within(right, left)


def _duplicates(items, label):
    seen, errors = set(), []
    for item in items:
        if item in seen:
            errors.append(f'{label}: duplicate {item!r}')
        seen.add(item)
    return errors


def _questions_errors(questions):
    errors = _duplicates((q['id'] for q in questions), 'questions.id')
    for question in questions:
        if question['type'] == 'choice':
            errors.extend(_duplicates((c['value'] for c in question['choices']),
                                      f"question {question['id']} choices.value"))
        if question['type'] == 'score':
            errors.extend(_duplicates((r['score'] for r in question['rubric']),
                                      f"question {question['id']} rubric.score"))
    return errors


def validate_input(data):
    """Check shape, IDs, scopes and provenance references, without judging."""
    errors = _schema_errors(data, 'input')
    if errors:
        return errors
    errors.extend(_questions_errors(data['questions']))
    errors.extend(_duplicates((s['id'] for s in data['sources']), 'sources.id'))
    unit, state = data['unit'], data['state']
    sources = {source['id']: source for source in data['sources']}
    subjects = unit['subjects']
    errors.extend(_duplicates((s['subject_id'] for s in subjects),
                              'unit.subjects.subject_id'))
    for source in data['sources']:
        for pointer in source['state_paths']:
            try:
                resolve_pointer(state, pointer)
            except ValueError as error:
                errors.append(f"source {source['id']} {pointer!r}: {error}")
        for pointer in source.get('locations', {}):
            try:
                resolve_pointer(state, pointer)
            except ValueError as error:
                errors.append(f"source {source['id']} location {pointer!r}: {error}")
            if not any(_within(pointer, p) for p in source['state_paths']):
                errors.append(f"source {source['id']} location outside source scope")
    for subject in subjects:
        try:
            resolve_pointer(state, subject['pointer'])
        except ValueError as error:
            errors.append(f"subject {subject['subject_id']}: {error}")
        for source_id in subject['source_ids']:
            if source_id not in sources:
                errors.append(f"subject {subject['subject_id']}: unknown source {source_id}")
            elif not any(_overlap(subject['pointer'], p)
                         for p in sources[source_id]['state_paths']):
                errors.append(f"subject {subject['subject_id']}: source {source_id} covers no part of subject")
    if unit['mode'] in ('row', 'group'):
        for i, subject in enumerate(subjects):
            for previous in subjects[:i]:
                if _overlap(subject['pointer'], previous['pointer']):
                    errors.append(f"subject {subject['subject_id']}: overlaps subject {previous['subject_id']}")
    known = {subject['subject_id'] for subject in subjects}
    for subject_id in unit.get('omitted_subject_ids', []):
        if subject_id not in known:
            errors.append(f'omitted subject {subject_id}: must be present in subjects')
    for join in unit.get('joins', []):
        for key in ('left_source_id', 'right_source_id'):
            if join[key] not in sources:
                errors.append(f'join {key}: unknown source {join[key]}')
    return errors


def validate_config(data):
    """Validate explicit mappings; never infer field types or token meanings."""
    errors = _schema_errors(data, 'config')
    if errors:
        return errors
    errors.extend(_questions_errors(data['questions']))
    columns = data.get('columns', [])
    for key in ('source', 'field'):
        errors.extend(_duplicates((c[key] for c in columns), f'columns.{key}'))
    for column in columns:
        true = set(column.get('true_values', []))
        false = set(column.get('false_values', []))
        null = set(column.get('null_tokens', []))
        if true & false or true & null or false & null:
            errors.append(f"column {column['field']}: overlapping boolean/null tokens")
        if column['type'] != 'boolean' and ('true_values' in column or 'false_values' in column):
            errors.append(f"column {column['field']}: boolean tokens require type boolean")
        if column['type'] not in ('date', 'datetime') and 'date_format' in column:
            errors.append(f"column {column['field']}: date_format requires date or datetime")
        if column['empty'] == 'preserve' and '' in null:
            errors.append(f"column {column['field']}: empty preserve conflicts with empty null token")
        if '' in true or '' in false:
            errors.append(f"column {column['field']}: empty cells cannot be boolean tokens")
    return errors


def invalid_result(reason='INVALID_FORMAT'):
    if reason not in INVALID_REASONS:
        raise ValueError('Unknown invalid-input reason code')
    return {'results': [{
        'subject_id': RESERVED, 'id': RESERVED, 'type': 'request',
        'status': 'invalid_input', 'value': None, 'reason_code': reason,
        'evidence': [], 'review_required': True,
    }]}


def _is_sentinel(output):
    rows = output.get('results', [])
    return (len(rows) == 1 and rows[0].get('reason_code') in INVALID_REASONS
            and output == invalid_result(rows[0]['reason_code']))


def _fact_matches(fact, actual):
    if isinstance(actual, str):
        # Empty evidence represents an actually empty scalar, not every string.
        return fact in actual if fact else actual == ''
    if actual is None or type(actual) in (bool, int, float):
        return fact == json.dumps(actual, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':'))
    return False


def validate_output(output, request=None):
    """Check syntax and, with a request, completeness and grounded evidence.

    Matching quoted bytes proves occurrence, not interpretation, source
    authenticity, business-rule compliance, or probability calibration.
    """
    errors = _schema_errors(output, 'output')
    if errors:
        return errors
    if request is not None and validate_input(request):
        return [] if _is_sentinel(output) else [
            'invalid request requires one __request__ invalid_input sentinel']
    if request is None:
        if any(r['subject_id'] == RESERVED or r['id'] == RESERVED
               for r in output['results']) and not _is_sentinel(output):
            errors.append('reserved IDs require the exact request-rejection sentinel')
        return errors
    subjects = {s['subject_id']: s for s in request['unit']['subjects']}
    questions = {q['id']: q for q in request['questions']}
    sources = {s['id']: s for s in request['sources']}
    expected = {(sid, qid) for sid in subjects for qid in questions}
    actual = [(r['subject_id'], r['id']) for r in output['results']]
    errors.extend(_duplicates(actual, 'results subject/question'))
    for pair in sorted(expected - set(actual)):
        errors.append(f'results: missing subject/question {pair!r}')
    for pair in sorted(set(actual) - expected):
        errors.append(f'results: unknown subject/question {pair!r}')
    omitted = set(request['unit'].get('omitted_subject_ids', []))
    for result in output['results']:
        sid, qid = result['subject_id'], result['id']
        prefix = f'result {sid}/{qid}'
        if sid not in subjects or qid not in questions:
            continue
        subject, question = subjects[sid], questions[qid]
        if result['type'] != question['type']:
            errors.append(f'{prefix}: type differs from question')
        if sid in omitted:
            if not (result['status'] == 'needs_review'
                    and result['reason_code'] == 'NOT_PROCESSED'
                    and result['evidence'] == []):
                errors.append(f'{prefix}: omitted subject requires empty NOT_PROCESSED review')
        elif result['reason_code'] == 'NOT_PROCESSED':
            errors.append(f'{prefix}: NOT_PROCESSED requires omitted_subject_ids membership')
        if result['status'] == 'decided':
            if question['type'] == 'choice' and result['value'] not in [c['value'] for c in question['choices']]:
                errors.append(f'{prefix}: value is not an allowed choice')
            if question['type'] == 'score' and (type(result['value']) not in (int, float)
                    or result['value'] not in [r['score'] for r in question['rubric']]):
                errors.append(f'{prefix}: value is not a rubric score')
            if request['unit']['mode'] == 'whole' and (
                    request['unit']['complete'] is not True
                    or any(sources[s]['complete'] is not True for s in subject['source_ids'])):
                errors.append(f'{prefix}: whole decision requires complete input and sources')
        if result['reason_code'] == 'CONDITION_ABSENT' and any(
                sources[s]['complete'] is not True
                for s in subject['source_ids'] if s in sources):
            errors.append(f'{prefix}: CONDITION_ABSENT requires complete=true for every subject source')
        if result['reason_code'] == 'LEDGER_MATCH':
            applicable = [e for e in ledger_entries(request['state'], subject['pointer'])
                          if e.get('question_id') == qid and not e.get('stale')]
            if not applicable:
                errors.append(f'{prefix}: LEDGER_MATCH requires an applicable ledger entry')
            elif result['value'] not in [e.get('value') for e in applicable]:
                errors.append(f'{prefix}: LEDGER_MATCH value differs from the ledger')
            if not any(sources.get(e['source_id'], {}).get('kind') == 'ledger' for e in result['evidence']):
                errors.append(f'{prefix}: LEDGER_MATCH requires evidence from a ledger source')
        for evidence in result['evidence']:
            source_id, location = evidence['source_id'], evidence['location']
            checked_scope = evidence.get('kind') == 'checked_scope'
            if source_id not in subject['source_ids']:
                errors.append(f'{prefix}: evidence source does not belong to subject')
                continue
            if not _within(location, subject['pointer']):
                errors.append(f'{prefix}: evidence is outside subject subtree')
            if not any(_within(location, p) for p in sources[source_id]['state_paths']):
                errors.append(f'{prefix}: evidence is outside source scope')
            try:
                value = resolve_pointer(request['state'], location)
            except ValueError as error:
                errors.append(f'{prefix}: evidence location {error}')
                continue
            if checked_scope:
                # Absence is grounded by the fully checked range, not a quote;
                # the schema pins fact to "" and the reason to CONDITION_ABSENT.
                continue
            if not _fact_matches(evidence['fact'], value):
                errors.append(f'{prefix}: fact is not an exact scalar quote at location')
    return errors


def ledger_entries(state, pointer):
    """Ledger records that recall injected under a subject (wrapper {input, ledger})."""
    try:
        node = resolve_pointer(state, pointer)
    except ValueError:
        return []
    if isinstance(node, dict) and set(node) == {'input', 'ledger'} and isinstance(node['ledger'], list):
        return [e for e in node['ledger'] if isinstance(e, dict)]
    return []


def explain_location(source, location):
    """Map a state pointer to the human-readable origin recorded in source.locations.

    Uses the longest recorded prefix; the remaining pointer tail is appended.
    Returns None when the source recorded no covering location.
    """
    locations = source.get('locations', {})
    prefixes = [p for p in locations if _within(location, p)]
    if not prefixes:
        return None
    prefix = max(prefixes, key=len)
    tail = location[len(prefix):]
    return f"{locations[prefix]} {tail}" if tail else locations[prefix]


def explain_evidence(output, request):
    """Human-readable origin for every evidence item; no validation here."""
    sources = {s['id']: s for s in request['sources']}
    rows = []
    for result in output['results']:
        for evidence in result['evidence']:
            source = sources.get(evidence['source_id'])
            rows.append({
                'subject_id': result['subject_id'], 'id': result['id'],
                'source_id': evidence['source_id'], 'location': evidence['location'],
                'source_location': explain_location(source, evidence['location']) if source else None,
                'kind': evidence.get('kind', 'quote'), 'fact': evidence['fact'],
            })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('input', 'config', 'output'))
    parser.add_argument('file', type=Path)
    parser.add_argument('--input', dest='request', type=Path,
                        help='Original request for output semantic guards')
    parser.add_argument('--explain', action='store_true',
                        help='With output --input: add human-readable evidence origins')
    args = parser.parse_args(argv)
    explain = None
    try:
        if args.explain and (args.kind != 'output' or args.request is None):
            raise ValueError('--explain requires output validation with --input')
        data = load_json(args.file)
        if args.request is not None and args.kind != 'output':
            errors = ['--input is only valid for output validation']
        elif args.kind == 'output':
            # A malformed JSON request is itself invalid, so only the sentinel
            # can be accepted. An unreadable path is an I/O error, not data.
            request = None
            malformed = False
            if args.request is not None:
                try:
                    request = load_json(args.request)
                except ValueError:
                    malformed = True
            # JSON null supplied as a request is malformed input, distinct
            # from omitting --input (syntax-only validation).
            errors = validate_output(
                data, {} if malformed or (args.request is not None and request is None) else request)
            if args.explain and not errors and not _is_sentinel(data):
                explain = explain_evidence(data, request)
        elif args.kind == 'input':
            errors = validate_input(data)
        else:
            errors = validate_config(data)
    except (OSError, ValueError, RecursionError) as error:
        errors = [str(error)]
    report = {'valid': not errors, 'errors': errors}
    if explain is not None:
        report['explain'] = explain
    print(json.dumps(report, ensure_ascii=False, allow_nan=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
