package main

import (
	"bufio"
	"fmt"
	"html/template"
	"os"
	"regexp"
	"strings"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/parser"
	"github.com/yuin/goldmark/renderer"
	ghtml "github.com/yuin/goldmark/renderer/html"
	"github.com/yuin/goldmark/util"
)

// HTML is markup we have generated ourselves and therefore trust.
type HTML = template.HTML

// MediaInfo carries the facts about an asset that only the encoder knew.
type MediaInfo struct {
	Width, Height int
	Has700        bool
}

// LoadMediaIndex reads the TSV the media pipeline emits. Keeping dimensions in a file
// means the generator never needs an image-decoding library, and every <img> can carry
// width/height so pages don't reflow as they load.
func LoadMediaIndex(path string) (map[string]MediaInfo, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	idx := map[string]MediaInfo{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "#") || strings.TrimSpace(line) == "" {
			continue
		}
		p := strings.Split(line, "\t")
		if len(p) < 4 {
			continue
		}
		idx[p[0]] = MediaInfo{Width: atoi(p[1]), Height: atoi(p[2]), Has700: p[3] == "1"}
	}
	return idx, sc.Err()
}

// ---------------------------------------------------------------- directives

var (
	faktaRe  = regexp.MustCompile(`(?ms)^:::fakta$\n(.*?)^:::$`)
	notisRe  = regexp.MustCompile(`(?ms)^:::notis$\n(.*?)^:::$`)
	videoRe  = regexp.MustCompile(`(?m)^:::video[ \t]+(\S+)[ \t]*$`)
	iframeRe = regexp.MustCompile(`(?s)<iframe[^>]*\ssrc="([^"]+)"[^>]*>\s*</iframe>`)
	titleRe  = regexp.MustCompile(`\stitle="([^"]*)"`)
	hostRe   = regexp.MustCompile(`^https?://(?:www\.|embed\.)?([^/]+)`)
)

// renderEmbedFacade replaces a third-party iframe with a placeholder that loads nothing.
// The archive sets no cookies of its own; an embed that silently contacts another site on
// page load would quietly undo that, so the visitor opts in per embed instead.
func renderEmbedFacade(tag, src string) string {
	host := src
	if m := hostRe.FindStringSubmatch(src); m != nil {
		host = m[1]
	}
	title := "Inbäddat innehåll"
	if m := titleRe.FindStringSubmatch(tag); m != nil && m[1] != "" {
		title = m[1]
	}
	esc := template.HTMLEscapeString
	return `<figure class="extern" data-inbaddning="` + src + `" data-titel="` + esc(title) + `">` +
		`<p class="extern-text">Filmen ligger hos <strong>` + esc(host) + `</strong> och laddas ` +
		`först när du klickar. Då kan ` + esc(host) + ` sätta kakor.</p>` +
		`<p class="extern-knappar">` +
		`<button type="button" class="extern-knapp">Visa filmen</button> ` +
		`<a class="extern-lank" href="` + src + `" rel="noopener">Öppna hos ` + esc(host) + `</a>` +
		`</p></figure>`
}

// pillClass distinguishes the two badge styles the original site used: concepts, and the
// grade levels an activity suits.
func pillClass(label string) string {
	if strings.HasPrefix(strings.ToLower(label), "ålder") {
		return "pill pill-ak"
	}
	return "pill"
}

func renderFakta(body string) string {
	var b strings.Builder
	b.WriteString(`<aside class="fakta">`)
	for _, line := range strings.Split(strings.TrimSpace(body), "\n") {
		label, value, ok := strings.Cut(line, ":")
		if !ok {
			continue
		}
		label, value = strings.TrimSpace(label), strings.TrimSpace(value)
		b.WriteString(`<div class="fakta-rad"><span class="fakta-etikett">` +
			template.HTMLEscapeString(label) + `</span><span class="fakta-varde">`)
		if strings.EqualFold(label, "fokus") {
			b.WriteString(template.HTMLEscapeString(value))
		} else {
			cls := pillClass(label)
			for _, item := range strings.Split(value, ",") {
				item = strings.TrimSpace(item)
				if item != "" {
					b.WriteString(`<span class="` + cls + `">` + template.HTMLEscapeString(item) + `</span>`)
				}
			}
		}
		b.WriteString(`</span></div>`)
	}
	b.WriteString(`</aside>`)
	return b.String()
}

func (r *docRenderer) renderVideo(src string) string {
	poster := strings.Replace(strings.TrimSuffix(src, ".mp4")+".jpg", "/video/", "/poster/", 1)
	info := r.media[src]
	dim := ""
	if info.Width > 0 {
		dim = fmt.Sprintf(` width="%d" height="%d"`, info.Width, info.Height)
	}
	return fmt.Sprintf(`<figure class="video"><video controls preload="none" playsinline`+
		` poster="%s"%s><source src="%s" type="video/mp4">`+
		`<p>Din webbläsare kan inte spela upp filmen. <a href="%s">Ladda ned den istället</a>.</p>`+
		`</video></figure>`, poster, dim, src, src)
}

// expandDirectives turns the three block directives into HTML before Markdown parsing.
// goldmark passes raw HTML blocks straight through, so this keeps the Markdown files
// readable without teaching the parser any custom syntax.
func (r *docRenderer) expandDirectives(md string) string {
	md = faktaRe.ReplaceAllStringFunc(md, func(m string) string {
		return renderFakta(faktaRe.FindStringSubmatch(m)[1])
	})
	md = notisRe.ReplaceAllStringFunc(md, func(m string) string {
		body := strings.TrimSpace(notisRe.FindStringSubmatch(m)[1])
		return `<aside class="notis">` + template.HTMLEscapeString(body) + `</aside>`
	})
	md = videoRe.ReplaceAllStringFunc(md, func(m string) string {
		return r.renderVideo(videoRe.FindStringSubmatch(m)[1])
	})
	md = iframeRe.ReplaceAllStringFunc(md, func(m string) string {
		return renderEmbedFacade(m, iframeRe.FindStringSubmatch(m)[1])
	})
	return md
}

// ---------------------------------------------------------------- markdown

type docRenderer struct {
	media map[string]MediaInfo
	md    goldmark.Markdown
}

func NewDocRenderer(media map[string]MediaInfo) *docRenderer {
	r := &docRenderer{media: media}
	r.md = goldmark.New(
		// WithAttribute enables `## Rubrik {.steg}`, which preserves the numbered
		// step headings the original theme styled with a CSS counter.
		goldmark.WithParserOptions(parser.WithAttribute()),
		goldmark.WithRendererOptions(
			// The classic editor relied on wpautop, where a single newline was a line
			// break; hard wraps reproduce that spacing exactly.
			ghtml.WithHardWraps(),
			ghtml.WithUnsafe(),
			renderer.WithNodeRenderers(util.Prioritized(&imageRenderer{media: media}, 100)),
		),
	)
	return r
}

func (r *docRenderer) Render(md string) (HTML, error) {
	var buf strings.Builder
	if err := r.md.Convert([]byte(r.expandDirectives(md)), &buf); err != nil {
		return "", err
	}
	return HTML(r.wrapFigures(buf.String())), nil
}

// imageRenderer emits responsive, self-sizing images in place of goldmark's bare <img>.
type imageRenderer struct{ media map[string]MediaInfo }

func (ir *imageRenderer) RegisterFuncs(reg renderer.NodeRendererFuncRegisterer) {
	reg.Register(ast.KindImage, ir.render)
}

func nodeText(n ast.Node, src []byte) string {
	var b strings.Builder
	_ = ast.Walk(n, func(c ast.Node, entering bool) (ast.WalkStatus, error) {
		if entering {
			if t, ok := c.(*ast.Text); ok {
				b.Write(t.Segment.Value(src))
			}
		}
		return ast.WalkContinue, nil
	})
	return b.String()
}

func (ir *imageRenderer) render(w util.BufWriter, src []byte, n ast.Node, entering bool) (ast.WalkStatus, error) {
	if !entering {
		return ast.WalkContinue, nil
	}
	img := n.(*ast.Image)
	dest := string(img.Destination)
	info := ir.media[dest]

	fmt.Fprintf(w, `<img src="%s"`, template.HTMLEscapeString(dest))
	if info.Has700 {
		small := strings.TrimSuffix(dest, ".webp") + "-700.webp"
		fmt.Fprintf(w, ` srcset="%s 700w, %s %dw" sizes="(max-width: 48rem) 100vw, 48rem"`,
			small, dest, info.Width)
	}
	if info.Width > 0 {
		fmt.Fprintf(w, ` width="%d" height="%d"`, info.Width, info.Height)
	}
	fmt.Fprintf(w, ` alt="%s" loading="lazy" decoding="async"`, template.HTMLEscapeString(nodeText(n, src)))
	if cap := string(img.Title); cap != "" {
		fmt.Fprintf(w, ` data-cap="%s"`, template.HTMLEscapeString(cap))
	}
	w.WriteString(">")
	return ast.WalkSkipChildren, nil
}

var loneImageRe = regexp.MustCompile(`(?s)<p>(<img [^>]*>)</p>`)
var capRe = regexp.MustCompile(` data-cap="([^"]*)"`)
var srcRe = regexp.MustCompile(`src="([^"]*)"`)

// proseWidth is the reading column in CSS pixels (--text: 46rem). An image wider than this
// is being shown scaled down, so opening the file itself actually reveals more detail.
const proseWidth = 736

// wrapFigures promotes an image that is alone in its paragraph to a <figure>, moving any
// caption into a <figcaption>. Doing this on our own output is simpler and safer than an
// AST transform, because the only <p><img></p> pairs in the document are ones we emitted.
//
// WordPress wrapped most of these images in a lightbox link, and several captions still
// tell the reader to click to enlarge. There is no lightbox here, so an image that is
// displayed smaller than it really is links to the file itself.
func (r *docRenderer) wrapFigures(h string) string {
	return loneImageRe.ReplaceAllStringFunc(h, func(m string) string {
		tag := loneImageRe.FindStringSubmatch(m)[1]
		caption := ""
		if c := capRe.FindStringSubmatch(tag); c != nil {
			caption = "<figcaption>" + c[1] + "</figcaption>"
			tag = capRe.ReplaceAllString(tag, "")
		}
		if src := srcRe.FindStringSubmatch(tag); src != nil {
			if info, ok := r.media[src[1]]; ok && info.Width > proseWidth {
				tag = `<a class="forstora" href="` + src[1] +
					`" target="_blank" rel="noopener" aria-label="Öppna bilden i full storlek">` +
					tag + `</a>`
			}
		}
		return "<figure>" + tag + caption + "</figure>"
	})
}
