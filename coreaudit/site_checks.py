"""Checks that need many pages (crawl) or outside data (keywords)."""
import re
from urllib.parse import urlparse

from .models import Finding
from .parse import GENERIC_H


def _path(u):
    p = urlparse(u).path or "/"
    return p if len(p) < 50 else p[:47] + "..."


def _ex(urls, n=3):
    s = ", ".join(_path(u) for u in urls[:n])
    return s + (f" and {len(urls) - n} more" if len(urls) > n else "")


def _share(bad, total):
    return f"{len(bad)} of {total} pages"


TITLE_MAX = 70      # characters; Google cuts by pixel width, ~60 is typical, 70 is clearly long
META_MAX = 170


def _t(p):
    return f'{_path(p["url"])}: "{p["title"][:75]}" ({len(p["title"])} characters)'


def crawl_findings(c: dict) -> list:
    allp = list(c["pages"].values())
    # Only grade real, indexable content pages. Archives (categories/tags), utility pages
    # (contact, thank-you, legal) and noindex pages are not judged like landing pages.
    pages = [p for p in allp if p.get("kind", "content") == "content" and not p["noindex"]]
    archives = [p for p in allp if p.get("kind") == "archive"]
    n = len(pages)
    out = []
    if not n:
        return out
    no_title = [p for p in pages if not p["title"]]
    no_meta = [p for p in pages if not p["meta_desc"]]
    no_h1 = [p for p in pages if not p["h1"]]
    multi_h1 = [p for p in pages if len(p["h1"]) > 1]
    generic = [p for p in pages if p["h1"] and GENERIC_H.match(p["h1"][0])]
    skips = [p for p in pages if any(b - a > 1 for a, b in zip(p["levels"], p["levels"][1:]))]
    thin = [p for p in pages if p["word_count"] < 150]
    long_t = [p for p in pages if len(p["title"]) > TITLE_MAX]
    long_m = [p for p in pages if len(p["meta_desc"]) > META_MAX]
    titles = {}
    for p in pages:
        if p["title"]:
            titles.setdefault(p["title"].strip().lower(), []).append(p)
    dup = {t: v for t, v in titles.items() if len(v) > 1}
    U = lambda ps: [p["url"] for p in ps]

    def add(id, area, title, bad, sev, why, fix, evidence=None, status="fail"):
        out.append(Finding(id=id, area=area, title=title, status=status, severity=sev, source="crawl",
                           evidence=evidence or f"{len(bad)} of {n} pages: {_ex(U(bad))}", why=why, fix=fix))

    if no_title:
        add("O-pages-title", "O", f"{len(no_title)} page(s) have no meta title", no_title, "high",
            "The meta title is the blue headline people click in Google.",
            "Give every page its own meta title with the topic and service.")
    if no_meta:
        add("O-pages-meta", "O", "Pages missing a meta description", no_meta, "medium",
            "Without one, Google writes its own snippet, usually a weak one, so fewer people click.",
            "Write about 140-160 characters per page that promise the result.", status="warn")
    if no_h1:
        add("E-pages-h1", "E", "Pages with no page headline (H1)", no_h1, "high",
            "The H1 is the main on-page headline. Google and visitors use it to understand the page.",
            "One clear H1 per page that includes the main topic.")
    if multi_h1:
        add("E-pages-multih1", "E", "Pages with more than one H1", multi_h1, "low",
            "Several H1s blur what the page is about.", "Keep one H1; turn the others into H2s.", status="warn")
    if generic:
        add("C-pages-generic", "C", "Page headlines (H1) that say nothing ('Welcome', 'Home', 'About us')", generic, "high",
            "Generic headlines waste the most valuable line on the page.",
            "Name who you help and the result, not the page type.",
            evidence="; ".join(f'{_path(p["url"])}: "{p["h1"][0][:50]}"' for p in generic[:3]))
    if skips:
        add("E-pages-skips", "E", "Headings out of order (H2 jumping to H4, for example)", skips, "low",
            "Usually means headings are used for their look instead of the page structure.",
            "Use H1, then H2, then H3 in order.", status="warn")
    if dup:
        shared = [x for v in dup.values() for x in v]
        t = next(iter(dup.values()))
        add("O-pages-duptitle", "O", "Different pages share the same meta title", shared, "medium",
            "Google cannot tell which page to show for a search, and the pages compete with each other.",
            "Give each page its own meta title.", status="warn",
            evidence=f'"{t[0]["title"][:70]}" is used on {len(t)} different pages: {_ex(U(t))}')
    if long_t:
        add("O-pages-longtitle", "O", "Meta titles that may be cut off in Google", long_t, "low",
            "Google shows roughly the first 60 characters, so the end of the title (often the service or city) can disappear.",
            "Keep the meta title around 50-60 characters, most important words first.", status="warn",
            evidence="; ".join(_t(p) for p in long_t[:2]) + (f" and {len(long_t) - 2} more" if len(long_t) > 2 else ""))
    if long_m:
        add("O-pages-longmeta", "O", "Meta descriptions that may be cut off in Google", long_m, "low",
            "Long descriptions get trimmed mid-sentence.", "Keep them near 150-160 characters.", status="warn")
    if thin:
        add("O-pages-thin", "O", "Pages with very little text", thin, "low",
            "Short pages rarely rank or persuade.", "Say who it is for, what you do, proof and the next step.", status="warn")
    if c["broken"]:
        b = c["broken"]
        add("E-broken", "E", f"{len(b)} broken internal link(s)", b, "high" if len(b) > 5 else "medium",
            "Visitors hit dead ends and Google loses trust in the site.", "Fix the link or redirect that address.",
            evidence="; ".join(f'{_path(x["url"])} ({x["status"]})' for x in b[:3]))
    soft = [p for p in archives if not p["noindex"] and p["word_count"] < 150]
    if len(soft) >= 8:
        add("E-archives", "E", f"{len(soft)} category/tag pages are open to Google with almost no content", soft, "low",
            "Category and tag pages are fine for organising a site, but thin ones add little value and can dilute your focus.",
            "Keep the categories you want to rank for and give them an intro and a unique title. Set the rest "
            "(especially tags and author pages) to noindex.", status="warn",
            evidence=f"{len(soft)} archive pages, for example {_ex(U(soft))}")

    def ok(id, area, title, evidence):
        out.append(Finding(id=id, area=area, title=title, status="pass", evidence=evidence, source="crawl"))
    if not no_title and not no_meta:
        ok("ok-pages-meta", "O", "Every page checked has a meta title and meta description", f"{n} pages checked")
    elif not no_title:
        ok("ok-pages-title", "O", "Every page checked has a meta title", f"{n} pages checked")
    if not no_h1 and not multi_h1 and not generic:
        ok("ok-pages-h1", "E", "Clean headline structure: one clear H1 per page", f"{n} pages checked")
    if not dup:
        ok("ok-pages-unique", "O", "Every page has its own meta title", f"{n} pages checked")
    if not c["broken"]:
        ok("ok-broken", "E", "No broken internal links found", f"{n} pages checked")
    return out


def keyword_findings(k: dict, facts, pages: dict) -> list:
    out = []
    if not k.get("ok"):
        return out
    items, total = k["items"], k["total"]
    nonbrand = [i for i in items if not i["brand"] and i["position"]]
    p1 = [i for i in nonbrand if i["position"] <= 10]
    near = sorted([i for i in nonbrand if 11 <= i["position"] <= 30 and i["volume"] >= 10],
                  key=lambda i: -i["volume"])
    if total == 0:
        out.append(Finding(id="E-kw-none", area="E", title="Google does not show your site for any searches we could find",
                           status="fail", severity="high", evidence="0 ranking keywords found.", source="keyword",
                           why="Nobody can find you unless they already know your name.",
                           fix="Build pages around what your customers actually search for."))
        return out
    if not p1:
        out.append(Finding(id="E-kw-brandonly", area="E", title="Only people who already know your name find you",
                           status="fail", severity="high", source="keyword",
                           evidence=f"{total} ranking keywords, none on page 1 outside your brand name.",
                           why="Growth comes from people who do not know you yet searching for what you sell.",
                           fix="Create or rewrite service pages around the searches your customers use."))
    else:
        top = sorted(p1, key=lambda i: -i["volume"])[:3]
        out.append(Finding(id="ok-kw-page1", area="E", title=f"You already show on page 1 for {len(p1)} non-brand search(es)",
                           status="pass", source="keyword",
                           evidence="; ".join(f'"{i["keyword"]}" (#{i["position"]}, {i["volume"]}/mo)' for i in top)))
    if near:
        out.append(Finding(id="E-kw-near", area="E", title="Searches you almost win, just off page 1", status="warn",
                           severity="medium", source="keyword",
                           evidence="; ".join(f'"{i["keyword"]}" (#{i["position"]}, {i["volume"]}/mo)' for i in near[:4]),
                           why="These are the quickest wins: Google already knows you are relevant.",
                           fix="Improve the ranking page: put the phrase in the title, H1 and a subheading, add depth, link to it."))
    # keyword used in the headline of the page that ranks for it
    miss = []
    for i in nonbrand[:12]:
        if not i["url"]:
            continue
        pg = next((p for u, p in pages.items() if urlparse(u).path.rstrip("/") == urlparse(i["url"]).path.rstrip("/")), None)
        if not pg:
            continue
        words = [w for w in re.findall(r"[a-z]{4,}", i["keyword"].lower())][:4]
        head = " ".join(pg["h1"] + pg["h2"][:4] + [pg["title"]]).lower()
        if words and not any(w in head for w in words):
            miss.append((i, pg))
    if miss:
        i, pg = miss[0]
        out.append(Finding(id="O-kw-headings", area="O", title="The page Google picks does not mention the search in its headings",
                           status="warn", severity="medium", source="keyword",
                           evidence=f'Ranks for "{i["keyword"]}" (#{i["position"]}) but its H1 is "{(pg["h1"] or ["none"])[0][:60]}" ({_path(i["url"])})',
                           why="When headings echo what people search, rankings and clicks rise.",
                           fix="Work the phrase naturally into the H1, title and a subheading."))
    b = k.get("backlinks")
    if b and b.get("referring_domains") is not None:
        rd = b["referring_domains"]
        out.append(Finding(id="E-links" if rd < 20 else "ok-links", area="E",
                           title="Few other sites link to you" if rd < 20 else "Other sites link to you",
                           status="warn" if rd < 20 else "pass", severity="medium", source="keyword",
                           evidence=f"{rd} websites link to you ({b.get('total')} links).",
                           why="Links from other sites are a trust signal Google weighs heavily.",
                           fix="Earn links from partners, directories, local organisations and press."))
    return out
