#!/usr/bin/env python3
"""
Fetch and re-encode the archive's media, driven by .work/media-manifest.tsv.

Downloads the best surviving source for each asset, then normalises it:
  images -> WebP at 1400w plus a 700w variant for srcset
  video  -> H.264 720p, faststart, with a poster frame
  docs   -> copied verbatim

Each asset has several candidate URLs (WordPress kept every resolution it generated).
We take the first that actually downloads, which is what silently repairs the handful of
references whose exact file is already 404 on the live server.

Writes .work/media-index.tsv (dest, width, height, has700) for the generator to size
images without needing an image library.

Stdlib + ffmpeg. Usage: python3 scripts/media.py [--force]
"""
import concurrent.futures as futures
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

MANIFEST = '.work/media-manifest.tsv'
INDEX = 'media/index.tsv'
SRC = '.work/src'
UA = 'kodknack-archive-import/1.0'

IMG_MAX, IMG_SMALL, IMG_Q = 1400, 700, 82
VID_MAX_H, VID_CRF = 720, 23


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f'{cmd[0]} failed: {" ".join(cmd[:6])}…\n{p.stderr[-600:]}')
    return p.stdout


def probe(path):
    """Return (width, height) of the first video stream."""
    out = run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
               'stream=width,height', '-of', 'json', path])
    st = json.loads(out)['streams'][0]
    return int(st['width']), int(st['height'])


def download(candidates, dest):
    """Try each candidate in order; return the local path of the first that works."""
    os.makedirs(SRC, exist_ok=True)
    for url in candidates:
        local = os.path.join(SRC, url.rsplit('/', 1)[-1])
        if os.path.exists(local) and os.path.getsize(local) > 0:
            return local, url
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as r, open(local, 'wb') as fh:
                shutil.copyfileobj(r, fh)
            if os.path.getsize(local) > 0:
                return local, url
            os.remove(local)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            if os.path.exists(local):
                os.remove(local)
    return None, None


def encode_image(src, dest):
    """Resize and encode to WebP with cwebp.

    ffmpeg is used only to read the source dimensions -- the Homebrew build here has no
    libwebp encoder, and cwebp produces smaller files anyway. Never upscale: an asset that
    is already narrower than the target is encoded at its native width.
    """
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    sw, sh = probe(src)

    def emit(width, out):
        cmd = ['cwebp', '-quiet', '-q', str(IMG_Q), '-metadata', 'none']
        if width < sw:
            cmd += ['-resize', str(width), '0']
        run(cmd + [src, '-o', out])

    target = min(IMG_MAX, sw)
    emit(target, dest)
    try:
        w, h = probe(dest)
    except (RuntimeError, KeyError, IndexError):
        w, h = target, max(1, round(sh * target / sw))

    small = dest.replace('.webp', f'-{IMG_SMALL}.webp')
    has_small = sw > IMG_SMALL
    if has_small:
        emit(IMG_SMALL, small)
    return w, h, has_small


def encode_video(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    run(['ffmpeg', '-nostdin', '-v', 'error', '-i', src,
         '-vf', f"scale='trunc(min(1,{VID_MAX_H}/ih)*iw/2)*2':'min({VID_MAX_H},ih)'",
         '-c:v', 'libx264', '-preset', 'slow', '-crf', str(VID_CRF), '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', '-y', dest])
    poster = dest.replace('/video/', '/poster/').replace('.mp4', '.jpg')
    os.makedirs(os.path.dirname(poster), exist_ok=True)
    try:
        run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', '1', '-i', dest,
             '-frames:v', '1', '-q:v', '3', '-y', poster])
    except RuntimeError:                       # clip shorter than a second
        run(['ffmpeg', '-nostdin', '-v', 'error', '-i', dest,
             '-frames:v', '1', '-q:v', '3', '-y', poster])
    return probe(dest) + (False,)


def main():
    force = '--force' in sys.argv
    rows = []
    with open(MANIFEST, encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('#') or not line.strip():
                continue
            dest, kind, cands = line.rstrip('\n').split('\t')
            rows.append((dest, kind, cands.split()))

    print(f'{len(rows)} assets to resolve')
    fetched, failed = {}, []
    with futures.ThreadPoolExecutor(max_workers=8) as pool:
        jobs = {pool.submit(download, c, d): (d, k) for d, k, c in rows}
        for i, fut in enumerate(futures.as_completed(jobs), 1):
            dest, kind = jobs[fut]
            local, url = fut.result()
            if local:
                fetched[dest] = (local, kind, url)
            else:
                failed.append(dest)
            if i % 25 == 0:
                print(f'  downloaded {i}/{len(rows)}')

    print(f'downloaded {len(fetched)}, unavailable {len(failed)}')
    index = []
    for n, (dest, (local, kind, url)) in enumerate(sorted(fetched.items()), 1):
        out = dest.lstrip('/')
        if os.path.exists(out) and not force:
            # Already encoded on an earlier run -- still needs an index entry, or the
            # generator loses the dimensions it uses to reserve layout space.
            if kind == 'doc':
                index.append((dest, 0, 0, False))
            else:
                w, h = probe(out)
                small = os.path.exists(out.replace('.webp', f'-{IMG_SMALL}.webp')) if kind == 'img' else False
                index.append((dest, w, h, small))
            continue
        try:
            if kind == 'img':
                w, h, small = encode_image(local, out)
            elif kind == 'video':
                w, h, small = encode_video(local, out)
            else:
                os.makedirs(os.path.dirname(out), exist_ok=True)
                shutil.copyfile(local, out)
                w = h = 0
                small = False
            index.append((dest, w, h, small))
            print(f'  [{n}/{len(fetched)}] {dest} ({w}x{h})' if w else f'  [{n}/{len(fetched)}] {dest}')
        except RuntimeError as e:
            failed.append(f'{dest}: {e}')

    with open(INDEX, 'w', encoding='utf-8') as fh:
        fh.write('# dest\twidth\theight\thas_700w\n')
        for dest, w, h, small in sorted(index):
            fh.write(f'{dest}\t{w}\t{h}\t{int(small)}\n')

    print(f'\nencoded {len(index)} assets -> {INDEX}')
    if failed:
        print(f'FAILED ({len(failed)}):')
        for f in failed:
            print('  ', f)


if __name__ == '__main__':
    main()
