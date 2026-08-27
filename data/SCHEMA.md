# Dataset schema

Built by `scripts/build_dataset.py`. Do not hand-edit files in `data/` — they are
regenerated. To correct a broker, edit `scripts/curated.json` and rebuild.

## Identity

| field | type | notes |
|---|---|---|
| `rank` | int | 1 = highest priority. Derived from `priority_score`. |
| `name` | string | Broker name as registered or published. |
| `dba` | string | Doing-business-as name, when different. |
| `domain` | string | Normalized primary domain. Used as the stable join key. |
| `website` | string | Primary website URL. |
| `category` | string | `people-search`, `face-search`, `phone-directory`, `b2b`, `marketing`, `public-record`. Present only where confidently classified. |

## Taking action

| field | type | notes |
|---|---|---|
| `opt_out_url` | string | Direct opt-out or privacy-rights page. |
| `search_url` | string | Template with `{first}` `{last}` `{city}` `{state}` for checking your own listing. Curated entries only. |
| `email` | string | Privacy contact. From the CA registry or verified directly. |
| `phone` | string | Registered contact number. |
| `verification` | string | What the broker requires: `email`, `phone`, `dob`, `photo-id`, `identity`, `none`. |
| `removal_method` | string | Usually `form`. |
| `notes` | string | Gotchas worth knowing before you start. |

## Leverage

| field | type | notes |
|---|---|---|
| `opt_out_hub` | string | The domain that actually processes this broker's opt-out, when it differs from its own. |
| `leverage` | int | How many brokers in this dataset route through the same hub. `5` means one submission clears five listings. |

See `leverage.json` for the full hub → brokers mapping.

## Disclosures (California registry, self-reported)

| field | type |
|---|---|
| `collects_minors` | bool |
| `collects_biometric` | bool |
| `collects_geolocation` | bool |
| `collects_reproductive_health` | bool |
| `collects_citizenship` | bool |
| `collects_sexual_orientation` | bool |
| `collects_gov_id` | bool |
| `sold_to_foreign_actor` | bool |
| `sold_to_federal_gov` | bool |
| `sold_to_law_enforcement` | bool |
| `sold_to_genai` | bool |

`sensitivity_score` (0–7) and `onward_sale_score` (0–4) are the counts of the
above two groups.

## Compliance (California registry, self-reported)

| field | type | notes |
|---|---|---|
| `deletion_requests_received` | int | Deletion requests received in the reporting year. Also used as a reach proxy. |
| `deletion_compliance_rate` | float | `(complied_whole + complied_part) / received`. `0.4` means 60% were denied. |
| `deletion_median_response_days` | float | Self-reported median response time. |

## Scoring

`priority_score` combines:

- **category weight** — how exposed the data is to a casual searcher
- **reach** — log-scaled `deletion_requests_received`, capped
- **leverage** — brokers cleared per submission
- **sensitivity + onward sale** — what they hold and who they sell it to
- **non-compliance** — denial rate, weighted by request volume so a 0% rate on
  three requests doesn't outrank a real signal
- small bonuses for being actionable now (has opt-out URL, email, search URL)

Non-compliance *raises* priority: a broker that denies half its requests needs
starting early and chasing.

## Provenance

`sources` is an array of: `cppa-registry-current`, `cppa-registry-historical`,
`curated`. Multiple values mean the record was merged across sources.
