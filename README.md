# Unlisted

**A free, open tool for getting yourself out of data broker databases.**

Removal services charge $20–130/year to do this. Most of what they do is send
form submissions and legal deletion letters, then follow up when brokers ignore
them. None of that requires a subscription — it requires a good list, the right
letter, and something to track the follow-ups. That's what this is.

- **882 data brokers**, ranked by how much they actually expose you
- **Built from public records** — primarily the California Data Broker Registry
- **Runs entirely in your browser.** No server, no account, no database
- **Drafts your deletion letters** with the statute your state actually gives you
- **Schedules follow-ups** at 30 / 45 / 90 / 120 days as a calendar file
- **Optional CLI** for people who want it automated locally

---

## Read this first: if you live in California, use DROP instead

California built a better version of this tool and made it free.

Under the **Delete Act**, the California Privacy Protection Agency operates
**DROP** — the Delete Request and Opt-Out Platform. You submit **one verified
request** and every data broker registered in California is legally required to
delete your personal information and stop selling or sharing it.

**→ https://privacy.ca.gov/drop/**

This is not a courtesy request that brokers may ignore:

- Since **August 1, 2026**, registered brokers must access DROP at least **every
  45 days**, process the deletion requests they find there, and report status.
- Non-compliance carries penalties of **$200 per request, per day**.
- It covers **500+ registered brokers** in a single submission.
- It handles cases this tool deliberately does not: a parent may submit for a
  child, and a family member may submit for an elderly relative.
- Several hundred thousand Californians have already used it.

**If you are a California resident, go do that first.** It is strictly better
than working through a list by hand, and it costs nothing. It would be dishonest
for this project to pretend otherwise.

### Then come back for the gaps

DROP is excellent and incomplete. Three things it does not do:

1. **Brokers that never registered in California.** DROP binds registrants only.
   Plenty of people-search sites simply don't register. Those are in this list.
2. **Verification.** DROP won't show you whether a specific listing actually came
   down. This tool tracks that per broker.
3. **Everyone outside California.** DROP is CA residents only. Connecticut has
   committed to a comparable portal but **not until 2028**. Texas and Oregon
   maintain broker registries with no unified deletion mechanism — you have to
   contact each broker yourself. That's what this is for.

---

## How to open it

There are three ways in, depending on how much you want to fuss. **All three run
the same code entirely inside your browser** — there is no version of this that
sends your data anywhere.

### 1. Just use the website (easiest)

If this repo has GitHub Pages enabled, the app is live at a normal URL:

```
https://YOURNAME.github.io/unlisted/
```

Visit it like any website. Nothing to install, no account. Despite being hosted,
your details never reach the server — GitHub is only serving static files, the
same way it would serve an image. Everything you type stays in your browser.

*To enable this on your own fork: Settings → Pages → Build from branch → `main`,
folder `/web`. It's free.*

### 2. Download one file and open it (most private)

Grab **`dist/unlisted.html`** from this repo and double-click it. That single
321 KB file contains the app, the styling, and all 882 brokers inlined.

It makes **zero network requests**. You can turn off your Wi-Fi entirely and it
still works. If you want the strongest possible guarantee that nothing leaks,
this is it — there is nothing for it to leak *to*.

### 3. Run it locally from the repo (for developers)

```bash
git clone https://github.com/YOURNAME/unlisted.git
cd unlisted
python3 -m http.server --directory web 8000
# open http://localhost:8000
```

Use this if you want to rebuild the dataset or modify the app.

---

## Does it save my progress?

**Yes.** Everything you mark is saved automatically in your browser as you go.
Close the tab, shut the laptop, come back next week — your details and every
broker's status are still there.

Some specifics worth knowing:

- It's stored in your browser's **`localStorage`**, on your machine only.
- It is **tied to one browser on one device.** Progress in Chrome on your laptop
  won't appear in Safari, or on your phone.
- **Clearing site data or cookies erases it.** So does private/incognito mode,
  which forgets everything when you close the window.
- Use **Export progress** for a backup, or to move to another browser or
  machine — then **Import progress** on the other side. The exported file
  contains the details you entered, so treat it like any personal document.

If you'd rather your progress live in a plain file you control instead of in a
browser, use the CLI — it stores state in `~/.config/unlisted/`.

---

## What it actually does — and what you still do yourself

**This is a workbench, not a robot.** It does the research, ranking, drafting and
scheduling. You do the clicking. That split is deliberate, not an unfinished
feature.

| Step | Who does it |
|---|---|
| Rank 882 brokers by how much they expose you | **The tool** |
| Search your name on each broker site | **You** |
| Decide whether a listing is actually you | **You** |
| Fill in the opt-out form, solve the CAPTCHA | **You** |
| Draft the deletion letter with your state's statute | **The tool** |
| Send the letter | **You**, from your own email |
| Track status and schedule follow-ups | **The tool** |

**Searching is manual and there is no way around it.** Each broker gets a "Check
listing" button that opens their search with your name filled in — you look at
the result and judge whether it's you. The tool doesn't automate this for two
reasons: broker search pages are protected against automated access, and more
importantly, **a name and an age cannot reliably distinguish you from a stranger
who shares them.** Filing a deletion request against someone else's record is a
real harm. Two seconds of your own eyes settles what no script can.

Realistically: budget **about an hour** for the top 20 brokers, then roughly
20 minutes every few months for follow-ups and listings that come back.

### What it can't do

- **Solve CAPTCHAs or complete phone verifications.** Those exist to stop
  automation. Working around them would violate terms of service and produce a
  tool that gets abused for worse things than privacy.
- **Actually delete you.** Opting out suppresses your listing on that broker's
  site. It does not touch public records, breach dumps already circulating, or
  private databases with no public interface. Anyone promising full erasure is
  selling something.

---

## CLI

```bash
python3 cli/unlisted.py init            # your details → ~/.config/unlisted (chmod 600)
python3 cli/unlisted.py list --top 25   # prioritized worklist
python3 cli/unlisted.py open spokeo.com # open that broker's opt-out page
python3 cli/unlisted.py letter mylife.com
python3 cli/unlisted.py mark mylife.com sent
python3 cli/unlisted.py due             # which follow-ups are due today
```

Optional: send letters through **your own** mail account. Credentials come from
the environment and are never written to disk.

```bash
export UNLISTED_SMTP_HOST=smtp.example.com
export UNLISTED_SMTP_USER=you@example.com
export UNLISTED_SMTP_PASS=...
python3 cli/unlisted.py send mylife.com
```

Run it monthly with cron:

```
0 9 1 * *  cd /path/to/unlisted && /usr/bin/python3 cli/unlisted.py due
```

---

## How your privacy is protected

This is a privacy tool, so the architecture is the feature. The design rule is
that **the project must never be technically capable of seeing your data.**

| | |
|---|---|
| **No server** | The web app is static files. There is no backend to breach or subpoena. |
| **No account** | Nothing to sign up for. No email collected, ever. |
| **No analytics** | No tracking scripts, no telemetry, no third-party requests except Google Fonts. |
| **One network request** | The app fetches `brokers.json`. That's it. Your details are never sent anywhere. |
| **You are your own agent** | Letters open in *your* mail client and send from *your* address. Under CCPA, an authorized agent acting for you can be required to produce signed permission — sending as yourself avoids that problem entirely. |
| **Local storage only** | Your details live in `localStorage` (web) or `~/.config/unlisted/config.json` with `0600` permissions (CLI). |

**Use an email alias** when contacting brokers. Several are known to add opt-out
contacts to marketing lists. Proton Pass, SimpleLogin, and iCloud Hide My Email
all provide these free.

### What this tool deliberately does not do

- **It does not scrape brokers.** It builds each site's search URL and hands it
  to you. A human eye is what keeps a same-name stranger's record from being
  mistaken for yours — and it avoids CAPTCHA-solving, anti-bot evasion, and
  terms-of-service violations.
- **It does not solve CAPTCHAs.** Those exist to stop automation, and defeating
  them is out of scope regardless of intent.
- **It does not promise removal.** Records repopulate. Breach dumps are
  permanent. The UI says *submitted* and *confirmed*, never *deleted forever*.

---

## The data

`data/brokers.json` and `data/brokers.csv` are built by
`scripts/build_dataset.py` from primary sources. Rebuild anytime:

```bash
python3 scripts/build_dataset.py --refresh
```

**Sources**, all public record or independently verified:

1. **California Data Broker Registry (current)** — every broker registered with
   the CPPA, including privacy contact email, rights URL, what categories of
   sensitive data they collect, who they sold it to, and **their own reported
   deletion-request compliance statistics**.
2. **California Data Broker Registry (historical, 2020–)** — catches brokers
   that registered previously and may still operate.
3. **`scripts/curated.json`** — hand-verified people-search opt-out URLs,
   confirmed against each company's own published pages. This covers the
   people-search sites that never register in California.

### What's unusual about this dataset

- **Leverage mapping.** Many separately-branded brokers share one opt-out
  backend — a single PeopleConnect suppression request clears Intelius,
  TruthFinder, Instant Checkmate, US Search and Addresses.com at once. See
  `data/leverage.json`.
- **Compliance scoring.** California requires brokers to report how many
  deletion requests they received and how many they denied. Some deny nearly
  all of them. That's surfaced per broker, and it *raises* priority — a broker
  that denies half its requests is one to start early and chase.
- **Reach weighting.** Priority uses log-scaled deletion-request volume as a
  proxy for how many real people a broker affects, rather than a hand-picked
  "top sites" list.

See `data/SCHEMA.md` for field documentation.

---

## Contributing

The most valuable contribution is **telling us when a link breaks.** Brokers
change their opt-out flows constantly, and that decay is the single biggest
maintenance problem for any tool like this.

Open an issue with the broker name and what happened, or edit
`scripts/curated.json` and send a PR. See `CONTRIBUTING.md`.

---

## Licenses

- **Code** — AGPL-3.0. Chosen deliberately: if someone runs a modified version
  as a service, they must publish their changes. This exists so people don't
  have to pay for basic privacy, and the license protects that.
- **Data** (`data/`) — CC BY-SA 4.0. Use it, including commercially; keep it
  open and credit the project.

---

## Credit where it's due

This project stands on work other people did first, and they deserve the credit
for making any of this tractable:

- **[Yael Grauer — Big Ass Data Broker Opt-Out List](https://github.com/yaelwrites/Big-Ass-Data-Broker-Opt-Out-List)**
  — the original, and still the most useful hand-maintained guide in this space.
  If you only read one other thing, read that.
- **[Optery's open data broker directory](https://github.com/optery/optery-data-brokers-directory)**
  — for demonstrating that a structured, machine-readable broker directory was
  worth building and publishing openly.
- **The [California Privacy Protection Agency](https://cppa.ca.gov/)** — for the
  Delete Act registry and DROP, which are the most consequential things to
  happen to consumer data privacy in the US, and which make this dataset possible.
- **The [Privacy Rights Clearinghouse](https://privacyrights.org/)** — for
  decades of advocacy and for tracking Delete Act implementation.
- **[EasyOptOuts](https://easyoptouts.com/)** — for showing that this can be
  done cheaply and honestly, at $20/year, without the marketing theater.

Unlisted's own broker list is built independently from public records rather
than copied from any of the above, but the idea that such a list *should* exist
and be free is theirs.

---

## Disclaimer

Not legal advice. Statute citations are provided for convenience and may not
reflect current law in your jurisdiction. Removing yourself from broker sites
does not remove you from public records, breach dumps already in circulation, or
private databases with no public interface. Anyone who tells you your data can be
fully erased is selling something.
