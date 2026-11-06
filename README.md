# C.O.R.E. Audit

A surface-level marketing audit organized by **C**lient, **O**ffer, **R**oute, **E**ngine.
Reads only what a visitor (and Google) can see. No Search Console or Analytics access needed.

Every finding shows the exact evidence found on the site. AI findings are dropped unless the quote
they cite really appears on the page (see `coreaudit/judge.py`).

## Run it (no local setup)
1. Repo > **Settings > Secrets and variables > Actions > New repository secret**. Add:
   - `PAGESPEED_API_KEY` (free from Google Cloud, optional but recommended)
   - `ANTHROPIC_API_KEY` (for the AI judge, optional)
2. Repo > **Actions > C.O.R.E. Audit > Run workflow**, type one or more domains, run.
3. Open the finished run and download **core-audit-results** (JSON + HTML per site, plus `summary.txt`).

## Run locally
```
pip install -r requirements.txt
python -m coreaudit --url example.com --no-ai
python -m pytest -q
```

## Web service (embedded on the website)
See `docs/DEPLOY.md`. `server/` is the FastAPI app: embeddable page, email gate, 2 checks per person/company, reports, AWeber.

## Layout
| File | Job |
|---|---|
| `safety.py` | Only public websites (blocks internal addresses) |
| `fetch.py` | Polite fetching, redirects re-checked |
| `parse.py` | HTML into facts (headings, CTAs, schema, NAP...) |
| `technical.py` | robots.txt, sitemap, HTTPS |
| `pagespeed.py` | Google PageSpeed (mobile + desktop) |
| `checks.py` | Rule-based findings by C.O.R.E. |
| `judge.py` | Claude reads the copy; quotes verified in code |
| `scoring.py` | Scores per area, "fix first", lead route |
| `report.py` | Simple HTML report (placeholder for the widget report) |

## Roadmap
- Phase 0: run on ~20 sites, compare with Johnnatan's own judgment, tune rules, measure cost.
- Phase 1: keyword visibility (DataForSEO or OpenRush API), multi-page crawl.
- Phase 2: web service + WordPress widget, email gate with consent, lead record + alert.
- Phase 3: AWeber / systeme.io, privacy and terms wording, launch.
