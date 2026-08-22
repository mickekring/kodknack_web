#!/usr/bin/env python3
"""
One-time importer: WordPress WXR export -> Markdown content tree + media manifest.

This script is run ONCE. Its output (content/**.md) becomes the permanent source of
truth and the .xml export is retired. It is kept in the repo for provenance only --
nothing at build time depends on it.

Stdlib only. Usage:  python3 tools/import_wxr.py kodknck.WordPress.2026-08-22.xml
"""
import html
import os
import re
import sys
import collections
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}
SITE = 'https://kodknack.kringen.se'
UPLOADS = SITE + '/wp-content/uploads/'

IMG_EXT = {'.jpg', '.jpeg', '.png'}
VID_EXT = {'.mp4', '.mov'}
DOC_EXT = {'.pdf', '.xlsx', '.pages'}

# WordPress-generated derivative suffixes we must strip to reach the original asset.
THUMB_RE = re.compile(r'-\d{2,4}x\d{2,4}$', re.I)
VIDVAR_RE = re.compile(r'-(?:360|480|720|1080)$', re.I)

# Concept/subject taxonomies, keyed by the WordPress category nicename.
# Anything this small is a Bee-Bot command symbol set inline in a code sequence, not a
# figure. The smallest true figure in the corpus is 70px wide.
ICON_MAX = 64

SUBJECTS = {'ma', 'tk', 'en'}
METHODS = {'programmering-utan-dator', 'visuell-programmering', 'textbaserad-programmering'}
CONCEPTS = {
    'algoritm', 'felsokning', 'funktioner', 'input-output', 'koordinatsystem', 'listor',
    'monster', 'problemlosning', 'repetition', 'simulera', 'slump-random', 'sortering',
    'stegvisa-instruktioner', 'symbolers-anvandning', 'variabler', 'villkor',
}


# --------------------------------------------------------------------------- media

class Media:
    """Maps WordPress upload URLs onto stable /media/... paths.

    Every asset is reduced to a *stem* (original name, derivative suffixes stripped) so
    that the five resolutions WordPress generated for each video collapse onto one entry,
    and so that a body reference to a file that no longer exists on the server still
    resolves -- the fetch step simply picks whichever candidate URL is actually alive.
    """

    def __init__(self):
        self.entries = {}       # dest path -> {'kind', 'stem', 'candidates': [url,...]}
        self._by_stem = {}      # (kind, stem) -> dest path
        self.unresolved = []

    @staticmethod
    def _stem_ext(url):
        name = url.rsplit('/', 1)[-1]
        base, ext = os.path.splitext(name)
        ext = ext.lower()
        base = THUMB_RE.sub('', base) if ext in IMG_EXT else base
        base = VIDVAR_RE.sub('', base) if ext in VID_EXT else base
        return base, ext

    def dest_for(self, url):
        """Return the /media/... path for an upload URL, registering it on first sight."""
        url = url.split('?', 1)[0]
        stem, ext = self._stem_ext(url)
        if ext in IMG_EXT:
            kind, folder, out_ext = 'img', 'img', '.webp'
        elif ext in VID_EXT:
            kind, folder, out_ext = 'video', 'video', '.mp4'
        elif ext in DOC_EXT:
            kind, folder, out_ext = 'doc', 'doc', ext
        else:
            self.unresolved.append(url)
            return None

        key = (kind, stem)
        if key not in self._by_stem:
            dest = f'/media/{folder}/{stem}{out_ext}'
            if dest in self.entries:      # different stem, same output name
                raise SystemExit(f'media filename collision on {dest} ({url})')
            self._by_stem[key] = dest
            self.entries[dest] = {'kind': kind, 'stem': stem, 'candidates': []}
        dest = self._by_stem[key]
        if url not in self.entries[dest]['candidates']:
            self.entries[dest]['candidates'].append(url)
        return dest

    def add_external(self, url, dest):
        """Register an asset that lives outside /wp-content/uploads/."""
        self.entries.setdefault(dest, {'kind': 'doc', 'stem': dest.rsplit('/', 1)[-1],
                                       'candidates': [url]})
        return dest

    def add_variants(self, urls):
        """Register the other resolutions WordPress generated for assets we already use.

        Only stems already referenced by the content are extended -- this is what gives the
        fetch step a fallback when the exact file named in a post body is gone from the
        server, without dragging in the ~340 attachments nothing links to.
        """
        for url in urls:
            stem, ext = self._stem_ext(url)
            kind = ('img' if ext in IMG_EXT else 'video' if ext in VID_EXT
                    else 'doc' if ext in DOC_EXT else None)
            dest = self._by_stem.get((kind, stem)) if kind else None
            if dest and url not in self.entries[dest]['candidates']:
                self.entries[dest]['candidates'].append(url)

    EXTERNAL = {SITE + '/gb.sjr': '/media/doc/gb.sjr'}

    def rewrite(self, text):
        """Point every reference at the archive: uploads -> /media/..., links -> root-relative."""
        def sub(m):
            return self.dest_for(m.group(0)) or m.group(0)
        text = re.sub(re.escape(UPLOADS) + r'[^\s"\'<>\)\]]+', sub, text)
        for url, dest in self.EXTERNAL.items():
            if url in text:
                text = text.replace(url, self.add_external(url, dest))
        # Cross-links between activities must not leave the site.
        return re.sub(re.escape(SITE) + r'(/[^\s)"\'<>\]]*)', r'\1', text)

    def write_manifest(self, path):
        # Prefer the highest-resolution candidate first; the fetcher takes the first
        # that actually downloads, which is what repairs the six dead references.
        def rank(u):
            base = u.rsplit('/', 1)[-1]
            for i, res in enumerate(('-1080.', '-720.', '-480.', '-360.')):
                if res in base:
                    return i + 2
            return 1 if base.lower().endswith('.mov') else 0
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# dest\tkind\tcandidate_urls (preference order)\n')
            for dest in sorted(self.entries):
                e = self.entries[dest]
                cands = sorted(e['candidates'], key=rank)
                fh.write(f'{dest}\t{e["kind"]}\t{" ".join(cands)}\n')
        return len(self.entries)


# ------------------------------------------------------------------ html -> markdown

class Prose(HTMLParser):
    """Converts the prose subset of the WordPress markup to Markdown.

    Structured chunks (code, tables, iframes, fact boxes, videos, captions) are lifted
    out into placeholders before this runs, so this only ever sees headings, emphasis,
    links, images and lists.
    """

    def __init__(self, media):
        super().__init__(convert_charrefs=True)
        self.media = media
        self.out = []
        self.lists = []          # stack of ['ul'|'ol', index]
        self.link = None         # (href, start_index_into_out)
        self.heading = None      # (level, start_index_into_out)
        self.emph = []           # stack of (delimiter, start_index_into_out)

    # -- helpers
    def emit(self, s):
        self.out.append(s)

    def block(self):
        """Ensure a blank line before the next block-level element."""
        txt = ''.join(self.out)
        if txt and not txt.endswith('\n\n'):
            self.emit('\n' if txt.endswith('\n') else '\n\n')

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.block()
            self.heading = (int(tag[1]), len(self.out), 'pk-heading-numbered' in (a.get('class') or ''))
            self.emit('#' * int(tag[1]) + ' ')
        elif tag in ('strong', 'b'):
            self.emph.append(('**', len(self.out)))
        elif tag in ('em', 'i'):
            self.emph.append(('*', len(self.out)))
        elif tag == 'a':
            self.link = (a.get('href', ''), len(self.out))
            self.emit('[')
        elif tag == 'img':
            src = a.get('src', '')
            alt = (a.get('alt') or '').replace(']', '')
            width = a.get('width')
            if width and width.isdigit() and int(width) <= ICON_MAX:
                h = a.get('height')
                dim = f' width="{width}"' + (f' height="{h}"' if h and h.isdigit() else '')
                self.emit(f'<img class="ikon" src="{src}"{dim} alt="{alt}">')
            else:
                self.emit(f'![{alt}]({src})')
        elif tag in ('ul', 'ol'):
            self.block()
            self.lists.append([tag, 0])
        elif tag == 'li':
            kind, n = self.lists[-1] if self.lists else ['ul', 0]
            if self.lists:
                self.lists[-1][1] = n = n + 1
            indent = '  ' * (len(self.lists) - 1)
            txt = ''.join(self.out)
            if txt and not txt.endswith('\n'):
                self.emit('\n')
            self.emit(f'{indent}{n}. ' if kind == 'ol' else f'{indent}- ')
        elif tag == 'p':
            self.block()
        elif tag == 'br':
            self.emit('\n')

    def handle_endtag(self, tag):
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level, start, numbered = self.heading or (2, len(self.out), False)
            body = ''.join(self.out[start + 1:]).strip()
            # A heading whose whole content is an image is not a heading at all.
            if re.fullmatch(r'!\[[^\]]*\]\([^)]*\)', body):
                del self.out[start:]
                self.emit(body)
            else:
                del self.out[start:]
                self.emit('#' * level + ' ' + body + (' {.steg}' if numbered else ''))
            self.heading = None
            self.emit('\n\n')
        elif tag in ('strong', 'b', 'em', 'i'):
            self.close_emphasis()
        elif tag == 'a':
            href, start = self.link or ('', len(self.out))
            body = ''.join(self.out[start + 1:]).strip()
            del self.out[start:]
            # Lightbox wrapper: <a href="full.jpg"><img src="large.jpg"></a> -> just the image.
            if re.fullmatch(r'!\[[^\]]*\]\([^)]*\)', body):
                self.emit(body)
            elif body:
                self.emit(f'[{body}]({href})')
            self.link = None
        elif tag in ('ul', 'ol'):
            if self.lists:
                self.lists.pop()
            self.emit('\n\n' if not self.lists else '\n')
        elif tag == 'li':
            txt = ''.join(self.out)
            if not txt.endswith('\n'):
                self.emit('\n')
        elif tag == 'p':
            self.emit('\n\n')

    def close_emphasis(self):
        """Emit an emphasis span with any inner whitespace moved outside the delimiters.

        WordPress content is full of `<strong>text </strong>` with the space inside. In
        Markdown a delimiter next to whitespace does not close the span, so the asterisks
        would render literally.
        """
        if not self.emph:
            return
        delim, start = self.emph.pop()
        body = ''.join(self.out[start:])
        del self.out[start:]
        core = body.strip()
        if not core:
            self.emit(body)
            return
        lead = body[:len(body) - len(body.lstrip())]
        trail = body[len(body.rstrip()):]
        self.emit(f'{lead}{delim}{core}{delim}{trail}')

    def handle_data(self, data):
        if self.lists and data.strip() == '':
            # Indentation between <li> elements is noise, but a space between two inline
            # elements inside an item is not -- dropping it would fuse "**visa** **siffra**".
            written = ''.join(self.out)
            if not written or written.endswith('\n'):
                return
            self.emit(' ')
            return
        self.emit(escape_asterisks(data))

    def result(self):
        return ''.join(self.out)


BULLET_RE = re.compile(r'^(\s*)\* ')


def escape_asterisks(text):
    """Escape literal asterisks, but leave a line-leading "* " working as a list bullet.

    The Läroplan excerpts use "* " bullets, which WordPress rendered as plain characters
    and Markdown can render properly. Everywhere else an asterisk is the author's own
    notation for an empty slot in a Scratch block, and must survive as text.
    """
    out = []
    for i, line in enumerate(text.split('\n')):
        m = BULLET_RE.match(line)
        if m:
            out.append(m.group(0) + line[m.end():].replace('*', '\\*'))
        else:
            out.append(line.replace('*', '\\*'))
    return '\n'.join(out)


def clean_markdown(md):
    """Tidy whitespace without disturbing the single-newline structure wpautop relied on."""
    md = md.replace(' ', ' ')
    md = re.sub(r'[ \t]+\n', '\n', md)
    md = re.sub(r'\n{3,}', '\n\n', md)
    md = re.sub(r'(?m)^[ \t]+$', '', md)
    return md.strip() + '\n'


# ------------------------------------------------------------- structured chunks

class Chunks:
    """Lifts non-prose structures out of the body so the Markdown pass can't mangle them."""

    def __init__(self):
        self.items = []

    def put(self, text, inline=False):
        self.items.append(text)
        tok = f'@@CHUNK{len(self.items) - 1}@@'
        return tok if inline else f'\n\n{tok}\n\n'

    def restore(self, md):
        return re.sub(r'@@CHUNK(\d+)@@', lambda m: self.items[int(m.group(1))], md)


def strip_tags(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s))


def normalise_badge(text):
    """Fix casing drift in the hand-typed fact-box badges."""
    text = re.sub(r'^Åk(\d)$', r'Åk \1', text.strip())
    canonical = {v.lower(): v for v in TAXONOMY['concepts'].values()}
    if text.lower() in canonical:
        return canonical[text.lower()]
    if text.isupper() and len(text) > 3:
        return text[:1] + text[1:].lower()
    return text


def extract_structures(body, chunks):
    """Replace code, tables, iframes, fact boxes, captions and videos with placeholders."""

    def code(m):
        return chunks.put('```\n' + strip_tags(m.group(1)).strip('\n') + '\n```')
    body = re.sub(r'<pre>\s*<code>(.*?)</code>\s*</pre>', code, body, flags=re.S)

    for pat in (r'<table.*?</table>', r'<iframe.*?</iframe>'):
        body = re.sub(pat, lambda m: chunks.put(m.group(0)), body, flags=re.S)

    def fakta(m):
        inner = m.group(1)
        fields = []
        for label, value in re.findall(r'<strong>\s*([^<:]+?)\s*:\s*</strong>(.*?)(?=<strong>|$)',
                                       inner, flags=re.S):
            badges = re.findall(r'<span class="pk-badge[^"]*">(.*?)</span>', value, flags=re.S)
            text = ', '.join(normalise_badge(strip_tags(b)) for b in badges) if badges \
                else ' '.join(strip_tags(value).split())
            if text:
                fields.append(f'{label.strip().lower()}: {text}')
        if not fields:                       # a plain bordered note, e.g. the Skolverket credit
            note = ' '.join(strip_tags(inner).split())
            return chunks.put(f':::notis\n{note}\n:::') if note else ''
        return chunks.put(':::fakta\n' + '\n'.join(fields) + '\n:::')
    body = re.sub(r'<div class="pk-content-block[^"]*">(.*?)</div>', fakta, body, flags=re.S)

    def caption(m):
        inner = m.group(1)
        img = re.search(r'<img[^>]*\ssrc="([^"]+)"', inner)
        if not img:
            return chunks.put(inner)
        # Whatever follows the image inside the shortcode is the caption text.
        tail = re.sub(r'<a[^>]*>.*?</a>|<img[^>]*/?>', '', inner, flags=re.S)
        tail = ' '.join(strip_tags(tail).split()).replace('"', "'")
        title = f' "{tail}"' if tail else ''
        return chunks.put(f'![]({img.group(1)}{title})')
    body = re.sub(r'\[caption[^\]]*\](.*?)\[/caption\]', caption, body, flags=re.S)

    # Videos appear two ways: an explicit shortcode, and a bare URL on its own line that
    # WordPress auto-embedded. Both become the same directive.
    body = re.sub(r'\[video[^\]]*\]\s*(\S+?)\s*\[/video\]',
                  lambda m: chunks.put(f':::video {m.group(1)}'), body, flags=re.S)
    body = re.sub(r'(?m)^[ \t]*(' + re.escape(UPLOADS) + r'\S+\.(?:mp4|mov))[ \t]*$',
                  lambda m: chunks.put(f':::video {m.group(1)}'), body, flags=re.I)
    return body


def extract_tabs(body):
    """Pull the Syfte / Läroplan tab block out into front-matter fields."""
    syfte = laroplan = ''
    m = re.search(r'\[powerkit_tabs.*?\[/powerkit_tabs\]', body, flags=re.S)
    if not m:
        return body, syfte, laroplan
    for title, inner in re.findall(r'\[powerkit_tab title="([^"]*)"\](.*?)(?=\[/powerkit_tab\]|\[powerkit_tab |\[/powerkit_tabs\])',
                                   m.group(0), flags=re.S):
        if title.strip().lower() == 'syfte':
            syfte = inner
        elif title.strip().lower().startswith('l'):
            laroplan = inner
    # The heading that introduced the tabs is redundant once they become fields.
    before, after = body[:m.start()], body[m.end():]
    before = re.sub(r'<h2[^>]*>\s*Syfte(?: och läroplan)?\s*</h2>\s*$', '', before.rstrip(),
                    flags=re.I)
    return before + after, syfte, laroplan


# ------------------------------------------------------------------ front matter

AUTHORS = {'cap-kodkna18': 'Micke Kring', 'cap-jonasj': 'Jonas Johansson'}
TAXONOMY = {'concepts': {}, 'subjects': {}, 'methods': {}}
GRADE_RE = re.compile(r'^ak-(\d)$')


def y_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def y_list(xs):
    return '[' + ', '.join(y_str(x) for x in xs) + ']'


def y_block(key, text):
    lines = text.rstrip().split('\n')
    return f'{key}: |\n' + '\n'.join('  ' + ln if ln.strip() else '' for ln in lines) + '\n'


def norm_title(t):
    t = ' '.join(t.split())
    return re.sub(r'\s+-\s+', ' – ', t)


def taxonomy(item):
    """Split the flat WordPress category soup into the axes the site actually uses."""
    out = {'grade': None, 'concepts': [], 'subjects': [], 'methods': [], 'authors': []}
    for c in item.findall('category'):
        dom, nice, name = c.get('domain'), c.get('nicename') or '', (c.text or '').strip()
        if dom == 'author':
            if nice in AUTHORS:
                out['authors'].append(AUTHORS[nice])
        elif dom == 'category':
            g = GRADE_RE.match(nice)
            if g:
                out['grade'] = int(g.group(1))
            elif nice in CONCEPTS:
                out['concepts'].append(nice)
                TAXONOMY['concepts'][nice] = name
            elif nice in SUBJECTS:
                out['subjects'].append(nice)
                TAXONOMY['subjects'][nice] = name
            elif nice in METHODS:
                out['methods'].append(nice)
                TAXONOMY['methods'][nice] = name
    for k in ('concepts', 'subjects', 'methods'):
        out[k] = sorted(set(out[k]))
    out['authors'] = sorted(set(out['authors']), reverse=True)   # Micke first
    return out


def convert_body(raw, media, chunks):
    body = extract_structures(raw, chunks)
    p = Prose(media)
    p.feed(body)
    p.close()
    return clean_markdown(chunks.restore(p.result()))


def convert_prose(raw, media):
    if not raw.strip():
        return ''
    p = Prose(media)
    p.feed(raw)
    p.close()
    return clean_markdown(p.result())


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'kodknck.WordPress.2026-08-22.xml'
    root = ET.parse(src).getroot().find('channel')

    attachments, all_urls, items = {}, [], []
    for it in root.findall('item'):
        pt = it.findtext('wp:post_type', namespaces=NS)
        if pt == 'attachment':
            url = it.findtext('wp:attachment_url', namespaces=NS)
            if url:
                attachments[it.findtext('wp:post_id', namespaces=NS)] = url
                all_urls.append(url)
        elif pt in ('post', 'page') and it.findtext('wp:status', namespaces=NS) == 'publish':
            items.append(it)

    media, docs = Media(), []
    for it in items:
        title = norm_title(it.findtext('title') or '')
        slug = it.findtext('wp:post_name', namespaces=NS) or ''
        raw = it.findtext('content:encoded', namespaces=NS) or ''
        if not raw.strip():
            continue                       # the theme-built front page; rebuilt as a template
        meta = {m.findtext('wp:meta_key', namespaces=NS): m.findtext('wp:meta_value', namespaces=NS)
                for m in it.findall('wp:postmeta', NS)}
        tax = taxonomy(it)
        raw, syfte_raw, laroplan_raw = extract_tabs(raw)

        chunks = Chunks()
        doc = {
            'title': title,
            'slug': slug,
            'date': (it.findtext('wp:post_date', namespaces=NS) or '')[:10],
            'grade': tax['grade'],
            'authors': tax['authors'],
            'concepts': tax['concepts'],
            'subjects': tax['subjects'],
            'methods': tax['methods'],
            'image': media.dest_for(attachments[meta['_thumbnail_id']])
                     if meta.get('_thumbnail_id') in attachments else None,
            'syfte': convert_prose(syfte_raw, media),
            'laroplan': convert_prose(laroplan_raw, media),
            'body': convert_body(raw, media, chunks),
        }
        if tax['grade'] is None:
            doc['kind'], doc['activity'] = 'page', None
        elif 'begrepp' in title.lower():
            doc['kind'], doc['activity'] = 'overview', 0
        else:
            n = re.search(r'Aktivitet\s+(\d+)', title, re.I)
            doc['kind'], doc['activity'] = 'activity', int(n.group(1)) if n else 99
        docs.append(doc)

    write_docs(media, docs, all_urls)


def write_docs(media, docs, all_urls):
    counts = collections.Counter()
    for d in docs:
        fm = ['---', f'title: {y_str(d["title"])}', f'slug: {y_str(d["slug"])}',
              f'kind: {d["kind"]}']
        if d['grade'] is not None:
            fm.append(f'grade: {d["grade"]}')
            fm.append(f'activity: {d["activity"]}')
        if d['date']:
            fm.append(f'date: {d["date"]}')
        for key in ('authors', 'concepts', 'subjects', 'methods'):
            if d[key]:
                fm.append(f'{key}: {y_list(d[key])}')
        if d['image']:
            fm.append(f'image: {y_str(d["image"])}')
        for key in ('syfte', 'laroplan'):
            if d[key].strip():
                fm.append(y_block(key, d[key]).rstrip('\n'))
        fm.append('---\n')

        text = media.rewrite('\n'.join(fm) + '\n' + d['body'])
        folder = f'content/ak-{d["grade"]}' if d['grade'] is not None else 'content/pages'
        os.makedirs(folder, exist_ok=True)
        with open(f'{folder}/{d["slug"]}.md', 'w', encoding='utf-8') as fh:
            fh.write(text)
        counts[d['grade'] if d['grade'] is not None else 'page'] += 1

    with open('content/taxonomy.yaml', 'w', encoding='utf-8') as fh:
        fh.write('# Slug -> display name, lifted verbatim from the WordPress categories.\n')
        for axis in ('concepts', 'subjects', 'methods'):
            fh.write(f'{axis}:\n')
            for slug in sorted(TAXONOMY[axis]):
                fh.write(f'  {slug}: {y_str(TAXONOMY[axis][slug])}\n')

    media.add_variants(all_urls)
    n = media.write_manifest('.work/media-manifest.tsv')
    print(f'wrote {len(docs)} documents')
    for k in sorted(counts, key=lambda x: (x == 'page', x)):
        print(f'  {"pages" if k == "page" else f"åk {k}":8} {counts[k]}')
    print(f'media: {n} distinct assets -> .work/media-manifest.tsv')
    if media.unresolved:
        print(f'UNRESOLVED media types: {sorted(set(media.unresolved))}')


if __name__ == '__main__':
    main()
