"""Opt-in accuracy reuse: verify existing envelopes, probe runtime, copy audit.

No scoring or inference policy lives here. Timing is always a fresh cohort.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

from .io import identity, read_json, require, sha256, within, write_json

REUSE = 'address-benchmark.accuracy-reuse/v1'


def plan_sources(source):
    path = Path(source).resolve()
    if path.is_dir():
        path = path / 'plan-results.json'
    source_pins = {str(path): sha256(path)}
    value = read_json(path)
    require(isinstance(value, dict), 'reuse plan object required')
    if value.get('schema') == 'address-benchmark.plan/v1':
        receipt_path = path.parent / 'plan-results.json'
        source_pins[str(receipt_path)] = sha256(receipt_path)
        receipt = read_json(receipt_path)
        require(isinstance(receipt, dict), 'reuse receipt object required')
        require(receipt['plan_sha256'] == sha256(path), 'reuse plan changed since execution')
        value = receipt
    require(value.get('schema') == 'address-benchmark.plan-results/v1', 'reuse requires an executed plan')
    ids, result = set(), {}
    for track in value['tracks']:
        require(track['id'] not in ids, 'duplicate reuse track')
        ids.add(track['id'])
        if track.get('status') == 'not-executed':
            continue
        directory = within(path.parent, track['output'])
        result[track['id']] = dict(directory=directory, content_id=track['content_id'])
    return dict(tracks=result, sources=source_pins)


def verified_source(source):
    from .runner import verify
    path = Path(source['directory']).resolve()
    verification = verify(path)
    require(verification['content_id'] == source['content_id'], 'reuse plan/run identity differs')
    report = read_json(path / 'run.json')
    require(report['content_id'] == verification['content_id'] == identity({k: v for k, v in report.items() if k != 'content_id'}), 'reuse source changed after verification')
    return path, report, verification


def _copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)  # independent copies, never hardlinks


def reuse_accuracy(source, engine, out, report, execute, *, samples, min_seconds, warmup, timeout):
    """Return a reused execution or a fixed, auditable reason to run fresh."""
    path, prior, verification = source
    name = engine['name']
    decision = dict(status='fresh', reason='no-matching-cell', source_content_id=prior['content_id'])
    if prior['corpus']['manifest_sha256'] != report['corpus']['manifest_sha256']:
        decision['reason'] = 'corpus-manifest-changed'
        return None, decision
    if prior['input_sha256'] != report['input_sha256'] or prior['artifacts']['references.jsonl'] != sha256(out / 'references.jsonl'):
        decision['reason'] = 'input-or-reference-panel-changed'
        return None, decision
    if (prior['source_pins'], prior['scorer'], prior['normalization'], prior.get('secondary_normalization')) != (report['source_pins'], report['scorer'], report['normalization'], report.get('secondary_normalization')):
        decision['reason'] = 'framework-or-policy-changed'
        return None, decision
    selected = [e for e in read_json(path / 'engines.json') if e['name'] == name]
    if selected != [engine]:
        decision['reason'] = 'engine-config-changed-or-added'
        return None, decision
    old = prior['accuracy'].get(name, {})
    if old.get('status') != 'ok':
        decision['reason'] = 'prior-cell-unsuccessful'
        return None, decision
    # Legacy runtime fingerprints omit the process environment, so they cannot
    # establish this contract merely by matching their partial identity.
    if 'environment_sha256' not in old['identity']:
        decision['reason'] = 'legacy-runtime-contract'
        return None, decision
    probe_directory = out / ('reuse-probe-' + name)
    probe = execute(engine, 'identity', out / 'inputs.jsonl', probe_directory,
                    samples=samples, min_seconds=min_seconds, warmup=warmup, timeout=timeout)
    write_json(probe_directory / 'execution.json', probe)
    if probe['status'] != 'ok' or probe.get('identity') != old['identity'] or probe.get('environment') != old.get('environment'):
        decision['reason'] = 'runtime-probe-mismatch'
        return None, decision
    command = engine.get('config', {}).get('command', [])
    if command:
        executable = shutil.which(command[0])
        if not executable or str(Path(executable).resolve()) not in old['identity']['declared_artifacts']:
            decision['reason'] = 'unverifiable-command-executable'
            return None, decision
    prefix = name + '-accuracy/'
    saved = out / 'reuse' / name
    saved.mkdir(parents=True)
    _copy(path / 'run.json', saved / 'source-run.json')
    _copy(path / 'engines.json', saved / 'source-engines.json')
    write_json(saved / 'source-verification.json', verification)
    directory = out / (name + '-accuracy')
    directory.mkdir()
    for relative in prior['artifacts']:
        if relative.startswith(prefix):
            if relative == prefix + 'execution.json':
                target = saved / 'source-execution.json'
            elif relative == prefix + 'cases.jsonl':
                target = saved / 'source-cases.jsonl'
            else:
                target = within(out, relative)
            # Source paths are constrained and copied only from the verified index.
            _copy(within(path, relative), target)
    copied = read_json(saved / 'source-run.json')
    consistent = copied == prior and sha256(saved / 'source-engines.json') == prior['artifacts']['engines.json']
    for relative, expected in prior['artifacts'].items():
        if relative.startswith(prefix):
            target = saved / 'source-execution.json' if relative == prefix + 'execution.json' else saved / 'source-cases.jsonl' if relative == prefix + 'cases.jsonl' else within(out, relative)
            consistent = consistent and sha256(target) == expected
    if not consistent:
        # Keep the rejected copies as audit, free only our new accuracy path.
        directory.rename(saved / 'rejected-accuracy')
        decision['reason'] = 'source-changed-during-copy'
        return None, decision
    entry = {key: deepcopy(old[key]) for key in ('status', 'identity', 'identity_sha256', 'output')}
    entry.update(command=[], exit_code=None, process_wall_ns=None, environment=probe['environment'],
                 origin=dict(schema=REUSE, kind='reused', source_content_id=prior['content_id'],
                             source_directory=str(saved.relative_to(out)), probe_directory=str(probe_directory.relative_to(out)),
                             source_exit_code=old.get('origin', {}).get('source_exit_code', old['exit_code'])))
    decision.update(status='reused', reason='verified-accuracy-cell')
    return entry, decision


def verify_reused(out, name, entry, report):
    """Verify provenance from retained copies without needing the original tree."""
    origin = entry['origin']
    require(origin['schema'] == REUSE and origin['kind'] == 'reused', 'reuse contract differs')
    saved = within(out, origin['source_directory'])
    source = read_json(saved / 'source-run.json')
    require(source['content_id'] == identity({k: v for k, v in source.items() if k != 'content_id'}) == origin['source_content_id'], 'reuse source content identity differs')
    require(source['source_pins'] == report['source_pins'] and source['corpus']['manifest_sha256'] == report['corpus']['manifest_sha256']
            and source['input_sha256'] == report['input_sha256'], 'reuse source contract differs')
    require(source['artifacts']['engines.json'] == sha256(saved / 'source-engines.json'), 'reuse source engine config changed')
    current = [e for e in read_json(out / 'engines.json') if e['name'] == name]
    previous = [e for e in read_json(saved / 'source-engines.json') if e['name'] == name]
    require(current == previous, 'reuse engine config differs')
    old = read_json(saved / 'source-execution.json')
    require(old == source['accuracy'][name] and old['status'] == 'ok', 'reuse source execution differs')
    require(origin['source_exit_code'] == old.get('origin', {}).get('source_exit_code', old['exit_code']), 'reuse source exit differs')
    require(entry['identity'] == old['identity'] and entry['identity_sha256'] == identity(entry['identity']), 'reuse runtime identity differs')
    probe_directory = within(out, origin['probe_directory'])
    probe = read_json(probe_directory / 'execution.json')
    probe_output = read_json(probe_directory / 'identity-probe.json')
    require(probe_output['schema'] == 'address-benchmark.identity-probe/v1' and probe_output['input_sha256'] == report['input_sha256'], 'reuse probe panel differs')
    require(read_json(probe_directory / 'identity.json') == probe['identity'] and identity(probe['identity']) == probe['identity_sha256'], 'reuse probe identity file differs')
    require(probe['status'] == 'ok' and probe['exit_code'] == 0 and probe['identity'] == entry['identity'] and
            probe['environment'] == entry['environment'] == old['environment'], 'reuse probe differs')
    prefix = name + '-accuracy/'
    for relative, expected in source['artifacts'].items():
        if relative.startswith(prefix):
            target = saved / 'source-execution.json' if relative == prefix + 'execution.json' else saved / 'source-cases.jsonl' if relative == prefix + 'cases.jsonl' else within(out, relative)
            require(sha256(target) == expected, 'reused source artifact differs')
    require(sha256(out / (name + '-accuracy') / 'cases.jsonl') == sha256(saved / 'source-cases.jsonl'), 'reused cases differ from source')
