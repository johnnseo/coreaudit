"""Rule-based C.O.R.E. checks. Every finding carries evidence taken from the site."""
import re

from .models import Finding
from .parse import GENERIC_H, Facts


def F(**kw):
    return Finding(**kw)


def run_rules(f: Facts, robots: dict, sitemap: dict, https: dict, speed: list, home_status: int) -> list:
    out = []
    h1s = [t for l, t in f.headings if l == 1]

    # ---------- CLIENT: who is this for, in whose words ----------
    if not h1s:
        out.append(F(id="C-h1-missing", area="C", title="No main headline (H1) on the home page", status="fail",
                     severity="high", evidence="No <h1> found.",
                     why="Visitors and Google both use the H1 to learn who the page is for and what it offers.",
                     fix="Add one H1 that names who you help and the result you deliver."))
    elif GENERIC_H.match(h1s[0]):
        out.append(F(id="C-h1-generic", area="C", title="Headline is generic ('Welcome to...')", status="fail",
                     severity="high", evidence=f'H1: "{h1s[0][:120]}"',
                     why="A welcome headline says nothing about the customer or the problem you solve.",
                     fix="Rewrite it as: who you help + the result + how. Lead with the customer, not your name."))
    else:
        out.append(F(id="C-h1-generic", area="C", title="Headline is not a generic welcome", status="pass",
                     evidence=f'H1: "{h1s[0][:120]}"'))
    if len(h1s) > 1:
        out.append(F(id="E-h1-multiple", area="E", title=f"{len(h1s)} H1 headings on the home page", status="warn",
                     severity="low", evidence=" | ".join(h[:60] for h in h1s[:4]),
                     why="Several H1s dilute the page's main message.", fix="Keep one H1 and demote the rest to H2."))

    welcome_hits = re.findall(r"(?i)\bwelcome to [^.]{0,60}", f.first_text)
    if welcome_hits:
        out.append(F(id="C-welcome-copy", area="C", title="Opening copy starts with 'Welcome to...'", status="fail",
                     severity="medium", evidence=f'"{welcome_hits[0].strip()}"',
                     why="Opening lines about the company instead of the customer lose attention in seconds.",
                     fix="Open with the customer's problem or goal."))

    # ---------- OFFER: is it clear, findable, specific ----------
    if not f.title:
        out.append(F(id="O-title-missing", area="O", title="No title tag", status="fail", severity="high",
                     evidence="No <title>.", why="The title is the clickable headline in Google results.",
                     fix="Write a title of 50-60 characters with your main service and location or audience."))
    else:
        n = len(f.title)
        st = "pass" if 30 <= n <= 65 else "warn"
        out.append(F(id="O-title-length", area="O", title="Title tag length", status=st, severity="medium",
                     evidence=f'"{f.title[:110]}" ({n} characters)',
                     why="Titles that are too short waste space; too long get cut off in results.",
                     fix="Aim for roughly 50-60 characters, main service first."))
    if not f.meta_desc:
        out.append(F(id="O-meta-missing", area="O", title="No meta description", status="fail", severity="medium",
                     evidence="No meta description.", why="Google writes its own snippet, often a poor one.",
                     fix="Write 140-160 characters that promise the result and invite the click."))
    if h1s and f.title:
        words = {w for w in re.findall(r"[a-z]{4,}", f.title.lower())}
        hw = {w for w in re.findall(r"[a-z]{4,}", h1s[0].lower())}
        if words and not (words & hw):
            out.append(F(id="O-keyword-heading", area="O", title="Title and H1 share no main words", status="warn",
                         severity="medium", evidence=f'Title: "{f.title[:70]}" / H1: "{h1s[0][:70]}"',
                         why="When the headline and title point different ways, search engines and visitors get a mixed signal.",
                         fix="Put your main service words in both the title and the H1."))
    h2s = [t for l, t in f.headings if l == 2]
    if f.word_count and not h2s:
        out.append(F(id="E-h2-missing", area="E", title="No H2 subheadings", status="warn", severity="low",
                     evidence=f"{f.word_count} words, no H2.", why="Subheadings let visitors and Google scan your offer.",
                     fix="Break the page into sections with descriptive H2s that include your services."))
    levels = [l for l, _ in f.headings]
    if any(b - a > 1 for a, b in zip(levels, levels[1:])):
        out.append(F(id="E-heading-skips", area="E", title="Heading levels are skipped", status="warn", severity="low",
                     evidence="Sequence: " + " > ".join(f"H{l}" for l in levels[:14]),
                     why="Skipped levels (H2 straight to H4) usually mean headings are used for styling.",
                     fix="Keep headings in order: H1, then H2, then H3."))
    if f.word_count < 250:
        out.append(F(id="O-thin-home", area="O", title="Very little copy on the home page", status="warn", severity="medium",
                     evidence=f"{f.word_count} words.", why="There may not be enough to explain the offer or rank for it.",
                     fix="Explain who it is for, what you do, proof, and the next step."))

    # ---------- ROUTE: how a visitor becomes a lead ----------
    cta_count = len(f.ctas)
    early = [c for c in f.ctas if c[2] <= 12]
    if cta_count == 0 and not f.forms and not f.tel_links:
        out.append(F(id="R-cta-none", area="R", title="No clear call to action found", status="fail", severity="high",
                     evidence="No action buttons, forms or phone links detected.",
                     why="Visitors who are ready have nowhere obvious to go.",
                     fix="Add one primary action (book, call, get a quote) near the top and repeat it down the page."))
    else:
        if not early and not f.tel_links:
            out.append(F(id="R-cta-late", area="R", title="No call to action near the top", status="warn", severity="medium",
                         evidence=f'First action found: "{f.ctas[0][0]}"' if f.ctas else "Only a form/phone further down.",
                         why="Many visitors never scroll.", fix="Put the primary action in the first screen."))
    if f.buttons_weak:
        out.append(F(id="R-cta-weak", area="R", title="Weak button wording", status="warn", severity="medium",
                     evidence="Buttons: " + ", ".join(f'"{b}"' for b in list(dict.fromkeys(f.buttons_weak))[:4]),
                     why="'Submit' and 'Learn more' say nothing about what the visitor gets.",
                     fix="Say the benefit: 'Get my free quote', 'Book my strategy call'."))
    labels = {c[0].lower() for c in f.ctas}
    if cta_count >= 6 and len(labels) >= 5:
        out.append(F(id="R-cta-competing", area="R", title="Many different actions compete for attention", status="warn",
                     severity="medium", evidence=f"{len(labels)} different action labels, e.g. " +
                     ", ".join(f'"{l}"' for l in list(labels)[:4]),
                     why="Too many choices lower conversions.", fix="Pick one primary action and one secondary."))
    if not f.phones and not f.tel_links and not f.mailto_links and not f.forms:
        out.append(F(id="R-contact-none", area="R", title="No way to contact you on the home page", status="fail",
                     severity="high", evidence="No phone, email or form detected.",
                     why="Reachability is the minimum for lead generation.", fix="Add a phone, email or form."))
    elif f.phones and not f.tel_links:
        out.append(F(id="R-tel-link", area="R", title="Phone number is not tap-to-call", status="warn", severity="low",
                     evidence=f"Phone text: {f.phones[0]}", why="Mobile visitors cannot tap to call.",
                     fix="Wrap the number in a tel: link."))
    if not f.viewport:
        out.append(F(id="R-mobile", area="R", title="Page may not be mobile friendly", status="fail", severity="high",
                     evidence="No viewport meta tag.", why="Most traffic is mobile.",
                     fix="Add a responsive viewport tag and a mobile-first layout."))

    # ---------- ENGINE: the systems that make it findable and trackable ----------
    if not robots["found"]:
        out.append(F(id="E-robots", area="E", title="No robots.txt file", status="fail", severity="medium",
                     evidence=f"/robots.txt returned {robots['status']}.", why="It tells search engines where the sitemap is.",
                     fix="Add a robots.txt that points to your sitemap."))
    elif robots["blocks_all"]:
        out.append(F(id="E-robots-block", area="E", title="robots.txt blocks the whole site", status="fail", severity="high",
                     evidence="Disallow: / for all crawlers.", why="Google cannot crawl your pages.",
                     fix="Remove the blanket Disallow unless the site is meant to be private."))
    else:
        out.append(F(id="E-robots", area="E", title="robots.txt found", status="pass", evidence="/robots.txt OK."))
    if not sitemap["found"]:
        out.append(F(id="E-sitemap", area="E", title="No XML sitemap found", status="fail", severity="medium",
                     evidence="Checked robots.txt, /sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml.",
                     why="A sitemap helps Google find and index every page.", fix="Generate and submit a sitemap."))
    else:
        out.append(F(id="E-sitemap", area="E", title="XML sitemap found", status="pass",
                     evidence=f"{sitemap['url']} ({sitemap['urls']} entries)"))
        if not sitemap.get("in_robots"):
            out.append(F(id="E-sitemap-robots", area="E", title="Sitemap is not listed in robots.txt", status="warn",
                         severity="low", evidence="No Sitemap: line.", why="Makes discovery easier.",
                         fix="Add a Sitemap: line to robots.txt."))
    if "noindex" in f.robots_meta:
        out.append(F(id="E-noindex", area="E", title="Home page is set to noindex", status="fail", severity="high",
                     evidence=f'Robots meta: "{f.robots_meta}"', why="Google is told not to show this page.",
                     fix="Remove noindex unless intentional."))
    if not f.canonical:
        out.append(F(id="E-canonical", area="E", title="No canonical tag", status="warn", severity="low",
                     evidence="Missing rel=canonical.", why="Duplicate URLs can split ranking signals.",
                     fix="Add a self-referencing canonical."))
    if not https["https_final"]:
        out.append(F(id="E-https", area="E", title="Site does not force HTTPS", status="fail", severity="high",
                     evidence="http:// version does not redirect to https://.", why="Browsers warn visitors; Google prefers HTTPS.",
                     fix="Install an SSL certificate and redirect all http to https."))
    for s in speed:
        if s.get("score") is None:
            continue
        sc = s["score"]
        st = "pass" if sc >= 90 else ("warn" if sc >= 50 else "fail")
        lcp = (s.get("lcp_ms") or 0) / 1000
        out.append(F(id=f"E-speed-{s['strategy']}", area="E", title=f"Speed on {s['strategy']}: {sc}/100", status=st,
                     severity="high" if sc < 50 else "medium", source="google",
                     evidence=f"Score {sc}/100, largest content shown in {lcp:.1f}s.",
                     why="Slow pages lose visitors and rank lower.", fix="Compress images, reduce plugins and scripts, use caching."))
    if not f.analytics:
        out.append(F(id="E-tracking", area="E", title="No analytics tag detected", status="warn", severity="medium",
                     evidence="No Google tag, GA4 or pixel found in the page source.",
                     why="Without tracking you cannot see what converts.", fix="Install GA4 and conversion tracking."))
    if not f.schema_types:
        out.append(F(id="E-schema", area="E", title="No structured data (schema)", status="warn", severity="low",
                     evidence="No JSON-LD found.", why="Schema helps Google show rich results.",
                     fix="Add Organization/LocalBusiness schema."))
    if not f.og.get("og:title") or not f.og.get("og:image"):
        out.append(F(id="E-social-preview", area="E", title="Social share preview is incomplete", status="warn",
                     severity="low", evidence=f"Open Graph tags: {', '.join(f.og) or 'none'}",
                     why="Links shared on social look bare.", fix="Add og:title, og:description and og:image."))
    if f.images_total and f.images_no_alt / f.images_total > 0.5:
        out.append(F(id="E-alt", area="E", title="Most images have no alt text", status="warn", severity="low",
                     evidence=f"{f.images_no_alt} of {f.images_total} images.",
                     why="Hurts accessibility and image search.", fix="Describe each meaningful image."))
    if not f.social_links:
        out.append(F(id="E-social-links", area="E", title="No social profile links on the site", status="warn", severity="low",
                     evidence="No links to Facebook, Instagram, LinkedIn, YouTube or TikTok.",
                     why="Visitors cannot verify you or follow you.", fix="Link your active profiles in header or footer."))
    # Local presence: NAP and map
    local_signal = bool(f.zips or "LocalBusiness" in f.schema_types)
    if local_signal:
        has_nap = bool(f.phones or f.tel_links) and bool(f.zips)
        out.append(F(id="E-nap", area="E", title="Name, address, phone visible on the page",
                     status="pass" if has_nap else "warn", severity="medium",
                     evidence=f"Phone: {(f.phones or f.tel_links or ['none'])[0]}; ZIP: {(f.zips or ['none'])[0]}",
                     why="Consistent name, address and phone feed local rankings.",
                     fix="Show the same business name, address and phone everywhere."))
        out.append(F(id="E-gbp-link", area="E", title="Google Maps / Business Profile linked or embedded",
                     status="pass" if f.has_map_or_gbp else "warn", severity="low",
                     evidence="Map link/embed found." if f.has_map_or_gbp else "No Google Maps link or embed found.",
                     why="Ties the site to your Google Business Profile.", fix="Embed your map and link your profile."))
    return out
