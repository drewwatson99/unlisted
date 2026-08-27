# Contributing

The highest-value contribution is **reporting a broken opt-out link.** Brokers
change their flows constantly and that decay is the main maintenance burden.

## Report a broken or changed opt-out

Open an issue with:

- Broker name and domain
- What you expected, and what actually happened
- The new URL, if you found it

## Add or fix a broker

Edit `scripts/curated.json`, then rebuild and open a PR:

```bash
python3 scripts/build_dataset.py
```

Minimum fields:

```json
{
  "name": "Example People Search",
  "website": "https://example.com",
  "domain": "example.com",
  "category": "people-search",
  "opt_out_url": "https://example.com/optout",
  "verification": "email",
  "removal_method": "form"
}
```

Add `search_url` with `{first}` `{last}` `{city}` `{state}` placeholders if the
site has a predictable search URL, and `notes` for anything surprising (expiring
links, phone verification, caps on requests per day).

**Verify against the broker's own site** before submitting. Please don't copy
entries out of another project's compilation — this dataset is built from
primary sources deliberately, and that's what keeps it freely licensable.

## Things we will not merge

- CAPTCHA-solving or anti-bot evasion, in any form
- Automated scraping of broker search pages
- Anything that transmits user data to a server
- Analytics or telemetry of any kind

These aren't style preferences. They're what makes the tool's privacy claim true
and keeps it on the right side of both the law and other people's terms.

## Code style

Standard library only where possible. No build step for the web app — it must
keep working as plain static files opened from disk.
