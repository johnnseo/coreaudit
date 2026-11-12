# Launch checklist (embed on athanmarketing.com)

The service is one small Python app (`server/`). It serves the embeddable page, runs the audits, enforces
2 checks per person and per company, saves every lead, and adds each person to AWeber with their results.

## 1. Host it on Render (about 20 minutes)
1. render.com > New > **Blueprint** > connect `johnnseo/coreaudit`. It reads `render.yaml`. Choose a paid plan (the
   free plan has no persistent disk, and leads would be lost on restart). Check current pricing.
2. When asked, fill the secrets: `ANTHROPIC_API_KEY`, `PAGESPEED_API_KEY`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`.
   Leave the AWeber ones empty for now.
3. Settings > Custom Domains > add `audit.athanmarketing.com`, then add the CNAME record Render shows at your DNS.
4. Open `https://audit.athanmarketing.com/embed`. You should see the page.
5. In Render > Environment, copy the generated `ADMIN_KEY` (you need it for steps 3 and 4 below).
   Your own email is in `ADMIN_EMAILS`, so you can test without using up the 2 checks.

## 2. Put it on WordPress
Edit the page > add a **Custom HTML** block > paste:
```html
<div id="core-audit"></div>
<script src="https://audit.athanmarketing.com/widget.js" async></script>
```
It resizes itself. If your theme blocks scripts in that block, use a plugin such as WPCode and paste the same code.

## 3. Connect AWeber
1. In AWeber: create a list (e.g. "C.O.R.E. Audit") and add 4 **custom fields**, exact names (lowercase):
   `site`, `score`, `fix_first`, `report_url`.
2. Create an app at labs.aweber.com. Set the redirect URL to
   `https://audit.athanmarketing.com/admin/aweber/callback`. Copy the client id and client secret.
3. Render > Environment: set `AWEBER_CLIENT_ID` and `AWEBER_CLIENT_SECRET`, wait for the redeploy.
4. Visit `https://audit.athanmarketing.com/admin/aweber/connect?key=YOUR_ADMIN_KEY`, log in to AWeber, approve.
5. Visit `https://audit.athanmarketing.com/admin/aweber/lists?key=YOUR_ADMIN_KEY`. It shows your account id and
   list id. Put them in `AWEBER_ACCOUNT_ID` and `AWEBER_LIST_ID`.
6. In AWeber, create an automation / campaign email that sends when someone is added with the tag `core-audit`.
   Put `{!cf_report_url}` in it as the "View my report" link. (That email is how the report link reaches their inbox.)
   Use tags to segment: `route-done_for_you`, `route-strategy_session`, `route-nurture`, `newsletter-optin`,
   `fix-first-C/O/R/E`.
7. Turn on **confirmed opt-in** in AWeber if you want double opt-in for the marketing list.

## 4. Check it works
- Run one audit with your own email. Look at the report, answer the 4 questions, then check the lead export:
  `https://audit.athanmarketing.com/admin/leads.csv?key=YOUR_ADMIN_KEY`
- Confirm the subscriber appears in AWeber with the custom fields. The `aweber` column in the CSV says `ok` or the error.

## Optional but recommended
- **Cloudflare Turnstile** (free human check): create a widget, set `TURNSTILE_SITEKEY` and `TURNSTILE_SECRET`.
- **Lead alerts**: set `ALERT_WEBHOOK_URL` to a Slack incoming webhook to get a message for every report and answer set.

## Limits (change in Render > Environment)
`MAX_AUDITS_PER_EMAIL=2`, `MAX_AUDITS_PER_DOMAIN=2`, `MAX_AUDITS_PER_IP_DAY=6`, `MAX_CONCURRENT_AUDITS=3`, `CRAWL_PAGES=15`.
Same person re-opening the same site gets the saved report and it is not counted again.

## Before launch (not legal advice)
Have your privacy policy mention: this tool, what is collected (name, email, website, city, answers, IP stored only
as a one-way hash), AI processing of public page text, AWeber and DataForSEO/Google as processors, how to unsubscribe
and delete data. Have a lawyer confirm consent wording for Spain/EU and the US.

## The Scorecard

The 12-question C.O.R.E. Scorecard runs in the same service, with the same branding, email-first form and AWeber list. It works two ways:

1. **On its own, as a simple free product.** Share `https://audit.athanmarketing.com/scorecard` anywhere, or embed it on a WordPress page:

```html
<div id="core-audit" data-magnet="scorecard"></div>
<script src="https://audit.athanmarketing.com/widget.js" async></script>
```

2. **As a bonus inside the website check.** Every audit report has a "Bonus: The C.O.R.E. Scorecard" box. The button opens the scorecard with no form, because we already have their name, email and consent. They go straight to the questions.

**Tracking where people came from.** Add `?src=name` to any link, for example `/scorecard?src=youtube` or `/scorecard?src=ig-bio`. On a WordPress page, `yourpage/?src=youtube` also works because the embed passes it through. Bonus users are tagged `audit-bonus` automatically.

**AWeber.** Scorecard subscribers get the tag `core-scorecard` (plus `fix-first-X` and `scorecard-low|mid|high`). Add an automation: when tag `core-scorecard` is applied, send an email with a link to `{!cf_report_url}`. The results page says "We also emailed you a link", so that automation must exist.

**Comparing.** Open `https://audit.athanmarketing.com/admin/ab?key=YOUR_ADMIN_KEY`. For each source and page it shows visitors, people who gave an email, and people who finished. `/admin/leads.csv` has `magnet` and `source` columns. Wait for about 100 visitors per source before drawing conclusions.

## The 11-minute video page

`https://audit.athanmarketing.com/watch` is the page the free video lives on. Video first (no email wall), a "do it while you watch" worksheet, a checklist PDF for an email, then the scorecard and the website check as next steps, and one quiet line about the workshop.

In Render, set:
- `VIDEO_ID` the YouTube id of the video (the part after `v=`). Until it is set the page shows a placeholder.
- `WORKSHOP_URL` the workshop page. Leave it empty to hide the workshop line.

Use `?src=` on the links you share (`/watch?src=youtube`, `/watch?src=ig-bio`); it shows up in `/admin/ab`.

**AWeber.** Sign-ups get the tag `core-checklist`. Add an automation: when that tag is applied, send an email linking to `https://audit.athanmarketing.com/checklist.pdf`. The page tells people a copy is on its way.

The checklist is built from the same tests as the scorecard. To change its wording, edit `server/static/checklist.html` and regenerate `server/static/core-checklist.pdf` (print `/checklist` to PDF, A4).
