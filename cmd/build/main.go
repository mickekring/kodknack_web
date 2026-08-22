// Command build turns content/ into a complete static site in dist/.
//
// It is a build-time tool only: nothing runs in production but a file server. Run it with
//
//	go run ./cmd/build
//
// and serve dist/ with anything at all.
package main

import (
	"fmt"
	"html/template"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
)

const (
	contentDir = "content"
	mediaIndex = "media/index.tsv"
	outDir     = "dist"
)

// PageData is the single shape every template receives.
type PageData struct {
	Site        *Site
	Doc         *Doc
	Grade       *Grade
	Term        *Term
	Prev, Next  *Doc
	Title       string
	Description string
	Canonical   string
	Section     string // drives the active state in the nav
}

func main() {
	log.SetFlags(0)
	if err := run(); err != nil {
		log.Fatalf("build failed: %v", err)
	}
}

func run() error {
	media, err := LoadMediaIndex(mediaIndex)
	if err != nil {
		return fmt.Errorf("media index: %w", err)
	}
	site, err := LoadSite(contentDir)
	if err != nil {
		return fmt.Errorf("content: %w", err)
	}

	rend := NewDocRenderer(media)
	for _, d := range site.Docs {
		if d.Body, err = rend.Render(d.Markdown); err != nil {
			return fmt.Errorf("%s: %w", d.Slug, err)
		}
		if d.SyfteH, err = rend.Render(d.Syfte); err != nil {
			return fmt.Errorf("%s syfte: %w", d.Slug, err)
		}
		if d.LaroplanH, err = rend.Render(d.Laroplan); err != nil {
			return fmt.Errorf("%s läroplan: %w", d.Slug, err)
		}
	}

	if err := os.RemoveAll(outDir); err != nil {
		return err
	}
	tpl, err := loadTemplates()
	if err != nil {
		return err
	}

	pages := 0
	emit := func(name, urlPath string, data PageData) error {
		data.Site = site
		data.Canonical = site.BaseURL + urlPath
		pages++
		return writePage(tpl, name, urlPath, data)
	}

	if err := emit("home", "/", PageData{
		Title:       site.Title + " – " + site.Tagline,
		Description: site.Tagline + ". " + site.Byline,
		Section:     "hem",
	}); err != nil {
		return err
	}

	for _, g := range site.Grades {
		grade := g
		if err := emit("grade", g.URL(), PageData{
			Grade:       grade,
			Title:       g.Name() + " – " + site.Title,
			Description: fmt.Sprintf("Aktiviteter och lärarhandledning för programmering i %s.", strings.ToLower(g.Name())),
			Section:     fmt.Sprintf("ak-%d", g.N),
		}); err != nil {
			return err
		}
		for _, d := range g.Docs() {
			prev, next := site.Siblings(d)
			if err := emit("post", d.URL(), PageData{
				Doc: d, Grade: grade, Prev: prev, Next: next,
				Title:       d.Title + " – " + site.Title,
				Description: summarise(d),
				Section:     fmt.Sprintf("ak-%d", g.N),
			}); err != nil {
				return err
			}
		}
	}

	for _, t := range site.Concepts {
		term := t
		if err := emit("concept", t.URL(), PageData{
			Term:        term,
			Title:       t.Name + " – " + site.Title,
			Description: fmt.Sprintf("Alla aktiviteter som arbetar med begreppet %s.", t.Name),
			Section:     "begrepp",
		}); err != nil {
			return err
		}
	}

	for _, d := range site.Pages {
		if err := emit("page", d.URL(), PageData{
			Doc: d, Title: d.Title + " – " + site.Title, Description: summarise(d),
			Section: d.Slug,
		}); err != nil {
			return err
		}
	}

	if err := emit("notfound", "/404.html", PageData{
		Title: "Sidan finns inte – " + site.Title, Section: "404",
	}); err != nil {
		return err
	}

	if err := writeSitemap(site); err != nil {
		return err
	}
	if err := writeRobots(site); err != nil {
		return err
	}
	for _, dir := range []string{"static", "media"} {
		if err := copyTree(dir, filepath.Join(outDir, staticDest(dir))); err != nil {
			return fmt.Errorf("copy %s: %w", dir, err)
		}
	}

	log.Printf("built %d pages, %d documents, %d concepts -> %s/", pages, len(site.Docs), len(site.Concepts), outDir)
	return nil
}

// staticDest keeps /media/... at the root while static/ contents are flattened into it.
func staticDest(dir string) string {
	if dir == "static" {
		return ""
	}
	return dir
}

func summarise(d *Doc) string {
	src := string(d.SyfteH)
	if strings.TrimSpace(src) == "" {
		src = string(d.Body)
	}
	txt := strings.Join(strings.Fields(stripTags(src)), " ")
	if len(txt) > 155 {
		if i := strings.LastIndex(txt[:155], " "); i > 60 {
			txt = txt[:i]
		} else {
			txt = txt[:155]
		}
		txt += "…"
	}
	return txt
}

func stripTags(s string) string {
	var b strings.Builder
	depth := 0
	for _, r := range s {
		switch {
		case r == '<':
			depth++
		case r == '>':
			if depth > 0 {
				depth--
			}
		case depth == 0:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func loadTemplates() (map[string]*template.Template, error) {
	funcs := template.FuncMap{
		"concepts": func(site *Site, slugs []string) []*Term { return site.ConceptNames(slugs) },
		"join":     strings.Join,
		"lower":    strings.ToLower,
	}
	out := map[string]*template.Template{}
	for _, name := range []string{"home", "grade", "post", "concept", "page", "notfound"} {
		t, err := template.New("base.html").Funcs(funcs).
			ParseFiles("templates/base.html", "templates/"+name+".html")
		if err != nil {
			return nil, fmt.Errorf("template %s: %w", name, err)
		}
		out[name] = t
	}
	return out, nil
}

// writePage maps a URL onto a file: "/" -> index.html, "/x/" -> x/index.html.
func writePage(tpl map[string]*template.Template, name, urlPath string, data PageData) error {
	rel := strings.Trim(urlPath, "/")
	dest := filepath.Join(outDir, "index.html")
	if strings.HasSuffix(urlPath, ".html") {
		dest = filepath.Join(outDir, rel)
	} else if rel != "" {
		dest = filepath.Join(outDir, rel, "index.html")
	}
	if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
		return err
	}
	f, err := os.Create(dest)
	if err != nil {
		return err
	}
	defer f.Close()
	return tpl[name].ExecuteTemplate(f, "base.html", data)
}

func writeSitemap(site *Site) error {
	var b strings.Builder
	b.WriteString(`<?xml version="1.0" encoding="UTF-8"?>` + "\n")
	b.WriteString(`<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">` + "\n")
	add := func(u string) {
		fmt.Fprintf(&b, "  <url><loc>%s%s</loc></url>\n", site.BaseURL, u)
	}
	add("/")
	for _, g := range site.Grades {
		add(g.URL())
		for _, d := range g.Docs() {
			add(d.URL())
		}
	}
	for _, t := range site.Concepts {
		add(t.URL())
	}
	for _, d := range site.Pages {
		add(d.URL())
	}
	b.WriteString("</urlset>\n")
	return os.WriteFile(filepath.Join(outDir, "sitemap.xml"), []byte(b.String()), 0o644)
}

func writeRobots(site *Site) error {
	body := "User-agent: *\nAllow: /\n\nSitemap: " + site.BaseURL + "/sitemap.xml\n"
	return os.WriteFile(filepath.Join(outDir, "robots.txt"), []byte(body), 0o644)
}

func copyTree(src, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, path)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if info.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		if strings.HasSuffix(path, ".tsv") { // build-time metadata, not part of the site
			return nil
		}
		in, err := os.Open(path)
		if err != nil {
			return err
		}
		defer in.Close()
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		out, err := os.Create(target)
		if err != nil {
			return err
		}
		defer out.Close()
		_, err = io.Copy(out, in)
		return err
	})
}
