"""Check inline local Markdown links in the root and recursively under docs."""

import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
files = sorted(root.glob('*.md')) + sorted((root/'docs').rglob('*.md'))
count = 0
for source in files:
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', source.read_text()):
        if '://' in target or target.startswith('mailto:'):
            continue
        path, _, anchor = target.partition('#')
        dest = (source.parent/path) if path else source
        if not dest.exists():
            raise SystemExit(f'{source.relative_to(root)}: missing target {target}')
        if anchor:
            headings = re.findall(r'^#+\s+(.+)$', dest.read_text(), re.M)
            slugs = [re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-') for heading in headings]
            if anchor not in slugs:
                raise SystemExit(f'{source.relative_to(root)}: missing anchor {target}')
        count += 1
print(f'Checked {count} local Markdown links/anchors.')
