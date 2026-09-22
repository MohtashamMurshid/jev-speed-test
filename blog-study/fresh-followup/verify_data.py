"""Independent, offline source/split checks. Does not invoke prepare.py."""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json
import unicodedata


def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def audit(root):
    study = root.parent
    source = list(csv.DictReader((study / 'test.csv').open()))
    old = json.loads((study / 'splits.json').read_text())
    used = {norm(x['text']) for rows in old.values() for x in rows}
    fresh = json.loads((root / 'cases.json').read_text())
    assert isinstance(fresh, list), 'cases must be a list'
    assert len(fresh) == 500
    assert len({x['id'] for x in fresh}) == 500
    assert len({norm(x['text']) for x in fresh}) == 500
    assert not ({norm(x['text']) for x in fresh} & used)
    labels = json.loads((study / 'categories.json').read_text())
    counts = collections.Counter(x['expected'] for x in fresh)
    assert set(counts) == set(labels)
    assert max(counts.values()) - min(counts.values()) <= 1
    by_text = collections.defaultdict(set)
    for i, row in enumerate(source):
        by_text[row['text']].add((f'test-{i}', row['category']))
    for row in fresh:
        assert row['text'] in by_text
        assert any(label == row['expected'] for _, label in by_text[row['text']])
        if row['id'].startswith('test-'):
            assert (row['id'], row['expected']) in by_text[row['text']]
    manifest = json.loads((study / 'data-manifest.json').read_text())
    verified_sources = {}
    for rel, digest in manifest['source_sha256'].items():
        path = study / Path(rel).name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == digest, rel
        verified_sources[rel] = actual
    return {'fresh_count': len(fresh), 'intents': len(counts),
            'min_per_intent': min(counts.values()), 'max_per_intent': max(counts.values()),
            'original_unique_texts_excluded': len(used),
            'normalized_overlap': 0, 'verified_source_hashes': verified_sources,
            'cases_sha256': hashlib.sha256((root / 'cases.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(audit(args.root), indent=2))
