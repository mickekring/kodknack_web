package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"gopkg.in/yaml.v3"
)

// Doc is one page of the archive: an activity, a grade overview, or a standalone page.
type Doc struct {
	Title    string   `yaml:"title"`
	Slug     string   `yaml:"slug"`
	Kind     string   `yaml:"kind"` // activity | overview | page
	Grade    *int     `yaml:"grade"`
	Activity int      `yaml:"activity"`
	Date     string   `yaml:"date"`
	Authors  []string `yaml:"authors"`
	Concepts []string `yaml:"concepts"`
	Subjects []string `yaml:"subjects"`
	Methods  []string `yaml:"methods"`
	Image    string   `yaml:"image"`
	Syfte    string   `yaml:"syfte"`
	Laroplan string   `yaml:"laroplan"`

	Markdown  string // body, after front matter
	Body      HTML
	SyfteH    HTML
	LaroplanH HTML
}

func (d *Doc) URL() string { return "/" + d.Slug + "/" }

// titlePrefix matches the "Åk 4 – Aktivitet 02 – " stem every post title carries. Only
// that stem is stripped, so a title that contains further dashes keeps all of its words.
var titlePrefix = regexp.MustCompile(`^Åk\s*\d+\s*–\s*(?:Aktivitet\s*\d+\s*–\s*)?`)

// Label is the short form used in listings, where the grade is already implied by context.
func (d *Doc) Label() string {
	if d.Kind == "page" {
		return d.Title
	}
	return strings.TrimSpace(titlePrefix.ReplaceAllString(d.Title, ""))
}

// Number is the two-digit step marker shown beside an activity in listings.
func (d *Doc) Number() string {
	if d.Kind != "activity" {
		return ""
	}
	return fmt.Sprintf("%02d", d.Activity)
}

// Term is one taxonomy entry (a concept, subject or method).
type Term struct {
	Slug, Name string
	Docs       []*Doc
}

func (t *Term) URL() string { return "/category/" + t.Slug + "/" }

// Grade collects everything taught in one årskurs.
type Grade struct {
	N          int
	Overview   *Doc
	Activities []*Doc
}

func (g *Grade) Name() string { return fmt.Sprintf("Årskurs %d", g.N) }
func (g *Grade) URL() string  { return fmt.Sprintf("/category/arskurs/ak-%d/", g.N) }

// Docs lists the overview first, then activities in numbered order -- the order the old
// site presented them in, and the order a teacher works through them.
func (g *Grade) Docs() []*Doc {
	out := make([]*Doc, 0, len(g.Activities)+1)
	if g.Overview != nil {
		out = append(out, g.Overview)
	}
	return append(out, g.Activities...)
}

// Taxonomy is the slug -> display-name map the importer lifted from WordPress.
type Taxonomy struct {
	Concepts map[string]string `yaml:"concepts"`
	Subjects map[string]string `yaml:"subjects"`
	Methods  map[string]string `yaml:"methods"`
}

// Site is the whole archive, assembled and cross-linked.
type Site struct {
	Title, Tagline, Byline, BaseURL string
	Grades                          []*Grade
	Concepts                        []*Term
	Pages                           []*Doc
	Docs                            []*Doc
	Tax                             Taxonomy
	byConcept                       map[string]*Term
}

func (s *Site) ConceptNames(slugs []string) []*Term {
	var out []*Term
	for _, sl := range slugs {
		if t := s.byConcept[sl]; t != nil {
			out = append(out, t)
		}
	}
	return out
}

// GradeOf finds the grade a document belongs to, for breadcrumbs and prev/next links.
func (s *Site) GradeOf(d *Doc) *Grade {
	if d.Grade == nil {
		return nil
	}
	for _, g := range s.Grades {
		if g.N == *d.Grade {
			return g
		}
	}
	return nil
}

// Siblings returns the previous and next document within the same grade.
func (s *Site) Siblings(d *Doc) (prev, next *Doc) {
	g := s.GradeOf(d)
	if g == nil {
		return nil, nil
	}
	docs := g.Docs()
	for i, x := range docs {
		if x.Slug != d.Slug {
			continue
		}
		if i > 0 {
			prev = docs[i-1]
		}
		if i < len(docs)-1 {
			next = docs[i+1]
		}
	}
	return prev, next
}

// baseURL is the only thing about this build that depends on where the site is deployed.
// It appears in canonical links, og:url, the sitemap and robots.txt -- everywhere an
// absolute address is unavoidable. Override it at build time when the hostname differs.
func baseURL() string {
	if v := strings.TrimRight(os.Getenv("KODKNACK_BASE_URL"), "/"); v != "" {
		return v
	}
	return "https://kodknack.kringen.se"
}

func splitFrontMatter(raw []byte) ([]byte, string, error) {
	s := string(raw)
	if !strings.HasPrefix(s, "---\n") {
		return nil, "", fmt.Errorf("missing front matter")
	}
	end := strings.Index(s[4:], "\n---\n")
	if end < 0 {
		return nil, "", fmt.Errorf("unterminated front matter")
	}
	return []byte(s[4 : 4+end+1]), s[4+end+len("\n---\n"):], nil
}

// LoadSite reads content/ into a fully cross-linked Site.
func LoadSite(dir string) (*Site, error) {
	site := &Site{
		Title:     "Kodknäck",
		Tagline:   "Progression och handledning inom programmering i grundskolan",
		Byline:    "En sajt av Micke Kring från tiden han jobbade på Årstaskolan",
		BaseURL:   baseURL(),
		byConcept: map[string]*Term{},
	}

	taxRaw, err := os.ReadFile(filepath.Join(dir, "taxonomy.yaml"))
	if err != nil {
		return nil, err
	}
	if err := yaml.Unmarshal(taxRaw, &site.Tax); err != nil {
		return nil, fmt.Errorf("taxonomy.yaml: %w", err)
	}

	byGrade := map[int]*Grade{}
	err = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.HasSuffix(path, ".md") {
			return err
		}
		raw, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		fm, body, err := splitFrontMatter(raw)
		if err != nil {
			return fmt.Errorf("%s: %w", path, err)
		}
		d := &Doc{}
		if err := yaml.Unmarshal(fm, d); err != nil {
			return fmt.Errorf("%s: %w", path, err)
		}
		d.Markdown = body
		site.Docs = append(site.Docs, d)

		switch {
		case d.Grade == nil:
			site.Pages = append(site.Pages, d)
		default:
			g := byGrade[*d.Grade]
			if g == nil {
				g = &Grade{N: *d.Grade}
				byGrade[*d.Grade] = g
			}
			if d.Kind == "overview" {
				g.Overview = d
			} else {
				g.Activities = append(g.Activities, d)
			}
		}
		return nil
	})
	if err != nil {
		return nil, err
	}

	for n := range byGrade {
		g := byGrade[n]
		sort.Slice(g.Activities, func(i, j int) bool { return g.Activities[i].Activity < g.Activities[j].Activity })
		site.Grades = append(site.Grades, g)
	}
	sort.Slice(site.Grades, func(i, j int) bool { return site.Grades[i].N < site.Grades[j].N })
	sort.Slice(site.Pages, func(i, j int) bool { return site.Pages[i].Slug < site.Pages[j].Slug })

	// Concept index, in the reading order of the grades so listings feel deliberate.
	for _, g := range site.Grades {
		for _, d := range g.Docs() {
			for _, slug := range d.Concepts {
				t := site.byConcept[slug]
				if t == nil {
					name := site.Tax.Concepts[slug]
					if name == "" {
						name = slug
					}
					t = &Term{Slug: slug, Name: name}
					site.byConcept[slug] = t
					site.Concepts = append(site.Concepts, t)
				}
				t.Docs = append(t.Docs, d)
			}
		}
	}
	sort.Slice(site.Concepts, func(i, j int) bool { return site.Concepts[i].Name < site.Concepts[j].Name })
	return site, nil
}

func atoi(s string) int { n, _ := strconv.Atoi(s); return n }
