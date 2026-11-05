"""Frozen gate policies over the existing case judgments; no inference or repair."""
from __future__ import annotations

import math

from .io import identity, require
from .scoring import GATE_METRICS, case_agreement, comparison

LEGACY_KEYS = {'candidate', 'max_losses', 'min_correct', 'min_preservation'}
THRESHOLDS = {'max_losses', 'max_loss_rate', 'min_correct', 'min_correct_rate', 'min_preservation', 'max_unit_false_positive_tokens'}
COUNTS = ('max_losses', 'min_correct', 'max_unit_false_positive_tokens')
SELECTORS = {'subset', 'cohort', 'splits', 'metric'}


def check_gate(gate, names, baseline):
    require(isinstance(gate, dict) and set(gate) <= {'candidate', 'metric', 'splits', 'requirements', *THRESHOLDS}
            and 'candidate' in gate, 'unknown gate settings or missing candidate')
    require(baseline in names and gate['candidate'] in names and baseline != gate['candidate'], 'gate needs selected baseline and distinct candidate')
    require(gate.get('metric', 'strict') in GATE_METRICS, 'unsupported gate metric')
    scopes = [gate]
    if 'requirements' in gate:
        require(isinstance(gate['requirements'], list) and gate['requirements'], 'nonempty gate requirements required')
        require(all(isinstance(r, dict) and set(r) <= THRESHOLDS | SELECTORS and set(r) & THRESHOLDS for r in gate['requirements']), 'gate scope needs supported thresholds/selectors')
        scopes += gate['requirements']
    require(set(gate) & THRESHOLDS or gate.get('requirements'), 'gate threshold required')
    for scope in scopes:
        require(not ('subset' in scope and 'cohort' in scope), 'choose a subset or cohort gate scope')
        require(scope.get('metric', gate.get('metric', 'strict')) in GATE_METRICS, 'unsupported gate metric')
        for key in ('subset', 'cohort'):
            require(key not in scope or isinstance(scope[key], str) and scope[key], 'nonempty gate selector required')
        if 'splits' in scope:
            require(isinstance(scope['splits'], list) and scope['splits'] and all(isinstance(x, str) and x for x in scope['splits'])
                    and len(set(scope['splits'])) == len(scope['splits']), 'unique gate splits required')
        for key in THRESHOLDS & set(scope):
            v = scope[key]
            require(type(v) in (int, float) and math.isfinite(v) and v >= 0, 'finite nonnegative gate threshold required')
            require(type(v) is int if key in COUNTS else v <= 1, 'gate count/rate threshold differs')


def resolve_cohorts(recipes, cases, baseline, accuracy, engine_configs, *, contract):
    """Baseline-only selection, recorded before any candidate-based analysis."""
    derived = any(isinstance(c['basis'], dict) and c['basis']['kind'] == 'baseline-correct' for c in recipes)
    require(not derived or baseline is not None, 'derived cohort requires a selected baseline')
    pin = None
    if baseline in accuracy and accuracy[baseline].get('status') == 'ok':
        pin = identity(dict(contract=contract, engine=next(e for e in engine_configs if e['name'] == baseline),
                            runtime_identity=accuracy[baseline]['identity_sha256']))
    result = []
    for recipe in recipes:
        basis = recipe['basis']
        if isinstance(basis, dict) and basis.get('baseline_pin') is not None:
            require(basis['baseline_pin'] == pin, 'cohort baseline pin differs')
        if isinstance(basis, dict) and basis['kind'] == 'baseline-correct':
            selected = [c for c in cases.get(baseline, []) if
                        ('subset' not in basis or basis['subset'] in c['subsets']) and
                        ('splits' not in basis or c['split'] in basis['splits']) and
                        case_agreement(c, basis.get('metric', 'strict')) is True]
            result.append(dict(id=recipe['id'], row_ids=[c['id'] for c in selected],
                basis={**basis, 'baseline_pin': pin}, status='resolved' if pin else 'baseline-unavailable'))
        else:
            result.append(dict(recipe, basis=basis if isinstance(basis, dict) else {'kind': 'external-unbound', 'description': basis}))
    return result


def _legacy(cases, gate, baseline, cohorts):
    if baseline not in cases or gate['candidate'] not in cases:
        return dict(status='failed', reason='accuracy-unavailable')
    _, paired = comparison(cases[baseline], cases[gate['candidate']], cohorts)
    correct = sum(c['primary_agrees'] is True for c in cases[gate['candidate']])
    retained = all(p['denominator'] > 0 and p['right_correct'] / p['denominator'] >= gate['min_preservation'] and
                   not p['right_unjudged'] for p in paired['preservation'].values())
    passed = (paired['judged_pairs'] > 0 and not paired['unmatched_judgments'] and paired['left_only'] <= gate['max_losses'] and
              correct >= gate['min_correct'] and retained and (bool(cohorts) or gate['min_preservation'] == 0))
    return dict(status='passed' if passed else 'failed', losses=paired['left_only'], correct=correct,
                judged_pairs=paired['judged_pairs'], preservation_passed=retained)


def accuracy_gate(cases, gate, baseline, cohorts):
    if gate is None:
        return dict(status='not-requested')
    if set(gate) == LEGACY_KEYS:
        return dict(_legacy(cases, gate, baseline, cohorts), policy='address-benchmark.gate/v1', metric='strict')
    if baseline not in cases or gate['candidate'] not in cases:
        return dict(status='failed', reason='accuracy-unavailable', policy='address-benchmark.gate/v2')
    left, right = cases[baseline], cases[gate['candidate']]
    require(len(left) == len(right) and all(a['id'] == b['id'] for a, b in zip(left, right)), 'gate case streams differ')
    cohort_map = {c['id']: c for c in cohorts}
    specs = ([{k: v for k, v in gate.items() if k in THRESHOLDS | {'metric', 'splits'}}]
             if set(gate) & THRESHOLDS else []) + gate.get('requirements', [])
    results = []
    for number, spec in enumerate(specs):
        metric = spec.get('metric', gate.get('metric', 'strict'))
        splits = spec.get('splits', gate.get('splits'))
        # Frozen reference labels define selectors; a typo or excluded split
        # must never turn into a vacuous pass.
        require(splits is None or set(splits) <= {c['split'] for c in left}, 'unknown gate split')
        require('subset' not in spec or any(spec['subset'] in c['subsets'] for c in left), 'unknown gate subset')
        require('cohort' not in spec or spec['cohort'] in cohort_map, 'unknown gate cohort')
        members = set(cohort_map[spec['cohort']]['row_ids']) if 'cohort' in spec else None
        chosen = [(a, b) for a, b in zip(left, right) if
                  (splits is None or a['split'] in splits) and
                  ('subset' not in spec or spec['subset'] in a['subsets']) and
                  (members is None or a['id'] in members)]
        values = [(case_agreement(a, metric), case_agreement(b, metric)) for a, b in chosen]
        judged = sum(a is not None and b is not None for a, b in values)
        mismatched = sum((a is None) != (b is None) for a, b in values)
        correct = sum(a is not None and b is True for a, b in values)
        losses = sum(a is True and b is False for a, b in values)
        passed = bool(judged) and not mismatched
        if 'max_losses' in spec: passed &= losses <= spec['max_losses']
        if 'max_loss_rate' in spec: passed &= bool(judged) and losses / judged <= spec['max_loss_rate']
        if 'min_correct' in spec: passed &= correct >= spec['min_correct']
        if 'min_correct_rate' in spec: passed &= bool(judged) and correct / judged >= spec['min_correct_rate']
        extra = {}
        if 'max_unit_false_positive_tokens' in spec:
            # Candidate-only token count over the selected rows with token references;
            # it can fail even when no row judgment changes.
            units = [b.get('unit_ownership') or {} for _, b in chosen]
            measured = [u for u in units if u.get('negative_tokens') is not None]
            extra = dict(unit_false_positive_tokens=sum(u['false_positive_tokens'] for u in measured),
                         unit_negative_tokens=sum(u['negative_tokens'] for u in measured), unit_token_rows=len(measured))
            passed &= bool(measured) and extra['unit_false_positive_tokens'] <= spec['max_unit_false_positive_tokens']
        preservation = []
        if spec.get('min_preservation', 0) > 0:
            eligible_ids = {a['id'] for a, _ in chosen}
            selected_cohorts = [cohort_map[spec['cohort']]] if 'cohort' in spec else cohorts
            for cohort in selected_cohorts:
                ids = set(cohort['row_ids']) & eligible_ids
                retained = sum(b is True for (a, _), (_, b) in zip(chosen, values) if a['id'] in ids)
                measured = sum(b is not None for (a, _), (_, b) in zip(chosen, values) if a['id'] in ids)
                ok = bool(ids) and measured == len(ids) and retained / len(ids) >= spec['min_preservation']
                preservation.append(dict(id=cohort['id'], denominator=len(ids), correct=retained, status='passed' if ok else 'failed'))
            passed &= bool(preservation) and all(c['status'] == 'passed' for c in preservation)
        results.append(dict(id=number + 1, status='passed' if passed else 'failed', metric=metric,
            rows=len(chosen), judged_pairs=judged, unmatched_judgments=mismatched, correct=correct, losses=losses,
            loss_rate=losses / judged if judged else None, correct_rate=correct / judged if judged else None,
            selector={k: spec[k] for k in ('subset', 'cohort') if k in spec}, splits=splits, preservation=preservation, **extra))
    return dict(status='passed' if all(r['status'] == 'passed' for r in results) else 'failed',
                policy='address-benchmark.gate/v2', metric=gate.get('metric', 'strict'), requirements=results)


def check_gate_context(gate, manifest, rows):
    if gate is None:
        return
    for spec in [gate, *gate.get('requirements', [])]:
        metric = spec.get('metric', gate.get('metric', 'strict'))
        require(not metric.startswith('strict-streetline/') or metric in manifest.get('scoring_profiles', []), 'gate profile not declared by corpus')
        require('splits' not in spec or set(spec['splits']) <= {r['split'] for r in rows}, 'unknown gate split')
        require('subset' not in spec or spec['subset'] in {s for r in rows for s in r['subsets']}, 'unknown gate subset')
        require('cohort' not in spec or spec['cohort'] in {c['id'] for c in manifest.get('preservation_cohorts', [])}, 'unknown gate cohort')
