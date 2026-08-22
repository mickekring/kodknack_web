# Kodknäck

A static archive of [kodknack.kringen.se](https://kodknack.kringen.se) — a progression for
teaching programming and computational thinking in Swedish primary school, grades 0–6, by
Micke Kring and Jonas Johansson at Årstaskolan.

The site stopped being updated in 2023, but teachers still use it. This rebuild exists so the
material survives without a CMS behind it: **no database, no admin, no cookies, no runtime.**
The deployed container is a web server and a folder of HTML files.

## How it fits together

```
content/        Markdown + YAML front matter — the source of truth
media/          Images, video, posters, documents (+ index.tsv with dimensions)
templates/      html/template files
static/         CSS, JS, self-hosted fonts, favicon
cmd/build/      The generator: content + templates -> dist/
tools/          One-time import from WordPress, and the site checker
scripts/        Media fetch and re-encode
```

Two dependencies, both effectively frozen: `goldmark` for Markdown and `yaml.v3` for front
matter. No npm, no framework, no CSS or JS build step.

## Everyday use

```sh
go run ./cmd/build          # content/ -> dist/
cd dist && python3 -m http.server 8000
python3 tools/check_site.py dist   # every internal link and asset must resolve
```

To fix a typo or add material, edit the Markdown in `content/` and rebuild. Nothing else is
needed — `content/` is authoritative, and the WordPress export has been retired.

### Content conventions

Standard Markdown, plus three block directives and one heading attribute:

````markdown
## Kör från garaget {.steg}      <!-- a numbered step; CSS supplies 01, 02, … -->

:::video /media/video/dice1.mp4  <!-- <video> with a poster frame -->

:::fakta                         <!-- the fact box under each Uppgift -->
begrepp: Villkor, Felsökning
fokus: Stegvisa instruktioner | Vad är kod?
ålder: Åk 2, Åk 3
:::

:::notis                         <!-- a plain bordered note -->
Dessa begreppsförklaringar kommer från Skolverkets webbkurs.
:::
````

An `<iframe>` in the content is automatically replaced with a click-to-load placeholder, so
no third party is contacted until the reader asks for it. An image that is wider than the
reading column is automatically linked to the full-size file, which is what the old
lightbox did and what several captions still tell the reader to expect.

**Keep each paragraph on one line.** Hard wraps are enabled so the imported WordPress
content keeps the line breaks `wpautop` gave it, which means a source line wrapped
mid-sentence renders as a `<br>` mid-sentence. Leave a blank line between paragraphs and
let the editor soft-wrap.

## Deploying

Built and deployed as a Docker image on Coolify. The image is `caddy:alpine` plus `dist/` —
the Go toolchain stays in the build stage.

```sh
docker build -t kodknack .
docker run -p 8080:80 kodknack
```

`Caddyfile` sets the security headers and the cache tiers (media and fonts immutable for a
year, CSS and JS an hour, pages revalidated). Coolify's proxy terminates TLS, so the container
listens on plain HTTP on port 80.

### Configuration

| Variable | When | Default | Purpose |
|---|---|---|---|
| `KODKNACK_BASE_URL` | **build** | `https://kodknack.kringen.se` | Absolute address baked into canonical links, `og:url`, `sitemap.xml` and `robots.txt` |
| `HSTS_MAX_AGE` | runtime | `31536000` | `Strict-Transport-Security` lifetime. Use `0` on a throwaway test hostname |

`KODKNACK_BASE_URL` is a **build argument**, not a runtime variable — the addresses are
written into the HTML when the site is generated, so changing it later has no effect until
the image is rebuilt. In Coolify, add it under environment variables and enable the
**Build Variable** toggle, otherwise it will be ignored.

`HSTS_MAX_AGE` is read by Caddy at startup and is an ordinary runtime variable. HSTS applies
to whichever hostname served the response, so a test deploy on a spare subdomain would
otherwise pin that subdomain to HTTPS for a year.

**Rate limiting belongs at the edge, not here.** A static site has no database, no login, no
forms and no server-side code, so the only real exposure is bandwidth on the video files.
Configure that in Coolify's proxy or Cloudflare — Caddy's rate limiter is a third-party module
that would require a custom `xcaddy` build for no benefit.

## Re-running the import

Neither of these is part of a normal build; they were run once and are kept for provenance.

The WordPress export is **not kept**: it carries author email addresses, this repo is public,
and `content/` has been the source of truth since the conversion. If the import ever needs to
run again, take a fresh export from the WordPress site (Tools → Export) and drop it in the
repo root — `.gitignore` already keeps `*.WordPress.*.xml` out of version control.

```sh
python3 tools/import_wxr.py kodknck.WordPress.2026-08-22.xml   # WXR -> content/
python3 tools/post_import_edits.py                             # the deliberate deviations
python3 scripts/media.py                                       # fetch + re-encode media
```

`import_wxr.py` **overwrites `content/`**, discarding anything edited since. Everything that
deliberately differs from WordPress lives in `post_import_edits.py`, so running the two in
order reproduces the committed tree exactly. `media.py` needs `ffmpeg` and `cwebp`.

## What changed from the original

- The 2 private posts and 2 `OLD |` drafts were work in progress and are not included.
- Six media references were already 404 on the live WordPress site; each now resolves to the
  highest surviving resolution of the same file.
- Both Replit embeds are dead and the projects are gone. The two Python programs were
  transcribed from the archive's own screenshots and are shown as code.
- The privacy pages described WordPress comments, Gravatar, Mailchimp and login logs, none of
  which exist any more. They were rewritten to describe the actual site.
- Fact-box labels had drifted over seven years (`ALGORITM` / `Algoritm`, `Åk5` / `Åk 5`) and
  were normalised against the real category names.
- Media went from 951 MB to 82 MB: unreferenced originals dropped, video re-encoded to 720p
  H.264, images to WebP.

Every original URL still resolves — teachers have been sharing these links for years.

## Licence

Site material: [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/deed.sv) unless
otherwise stated. Fonts (Space Grotesk, Source Serif 4, IBM Plex Mono) are SIL OFL.
