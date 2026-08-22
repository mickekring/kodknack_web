#!/usr/bin/env python3
"""
Verify the generated site: every internal reference resolves, and nothing reaches out
to a third party that we did not intend.

This is the check that proves the WordPress link rot is actually gone -- the old site
still serves several 404s, and a silent 404 in an archive is indistinguishable from
content that was never migrated.

Usage: python3 tools/check_site.py [dist]
"""
import os
import re
import sys
import collections

REF_RE = re.compile(r'(?:href|src)="([^"]+)"|<source[^>]+src="([^"]+)"')
# Third parties the content genuinely points at; anything else is a regression.
ALLOWED_HOSTS = {
    'scratch.mit.edu', 'makecode.microbit.org', 'embed.ur.se', 'replit.com', 'repl.it',
    'creativecommons.org', 'sv.wikipedia.org', 'www.pts.se', 'seti.org',
    'arstaskolan.stockholm.se', 'automattic.com', 'mailchimp.com', 'kodknack.se',
    'www.skolverket.se', 'kodknack.kringen.se',
}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else 'dist'
    pages, refs = [], []
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith('.html'):
                pages.append(os.path.join(dirpath, f))

    external = collections.Counter()
    broken = []
    for page in pages:
        html = open(page, encoding='utf-8').read()
        for m in REF_RE.finditer(html):
            url = m.group(1) or m.group(2)
            if not url or url.startswith(('#', 'data:', 'mailto:')):
                continue
            if url.startswith(('http://', 'https://', '//')):
                host = re.sub(r'^(?:https?:)?//([^/]+).*', r'\1', url)
                external[host] += 1
                continue
            refs.append((page, url))

    for page, url in refs:
        path = url.split('#', 1)[0].split('?', 1)[0]
        target = os.path.join(root, path.lstrip('/')) if path.startswith('/') \
            else os.path.normpath(os.path.join(os.path.dirname(page), path))
        if os.path.isdir(target):
            target = os.path.join(target, 'index.html')
        if not os.path.exists(target):
            broken.append((os.path.relpath(page, root), url))

    print(f'pages          : {len(pages)}')
    print(f'internal refs  : {len(refs)}')
    print(f'broken refs    : {len(broken)}')
    for page, url in broken[:30]:
        print(f'    {page}  ->  {url}')

    print('\nexternal hosts referenced:')
    bad_hosts = []
    for host, n in external.most_common():
        flag = '' if host in ALLOWED_HOSTS else '   <-- UNEXPECTED'
        if flag:
            bad_hosts.append(host)
        print(f'    {n:4}  {host}{flag}')

    # Assets that shipped but nothing points at -- dead weight in the image.
    used = {os.path.normpath(os.path.join(root, u.lstrip('/')))
            for _, u in refs if u.startswith('/media/')}
    on_disk = set()
    for dirpath, _, files in os.walk(os.path.join(root, 'media')):
        for f in files:
            on_disk.add(os.path.normpath(os.path.join(dirpath, f)))
    # -700 variants are reached through srcset, which this crude scan does not parse.
    orphans = {p for p in on_disk - used if '-700.webp' not in p and '/poster/' not in p}
    print(f'\nmedia on disk  : {len(on_disk)}')
    print(f'unreferenced   : {len(orphans)}')
    for p in sorted(orphans)[:10]:
        print(f'    {os.path.relpath(p, root)}')

    if broken or bad_hosts:
        print('\nFAIL')
        return 1
    print('\nOK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
