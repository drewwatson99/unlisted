#!/usr/bin/env python3
"""
unlisted — a local-first CLI for working through data broker opt-outs.

Everything stays on this machine. Your details live in a config file you
control; letters are written to disk or sent through your own SMTP account.
Nothing is transmitted to any service operated by this project, because no
such service exists.

Quick start:

    python3 cli/unlisted.py init
    python3 cli/unlisted.py list --top 25
    python3 cli/unlisted.py open whitepages.com
    python3 cli/unlisted.py letter whitepages.com
    python3 cli/unlisted.py mark whitepages.com sent
    python3 cli/unlisted.py due
    python3 cli/unlisted.py send whitepages.com        # optional, your SMTP

Run `python3 cli/unlisted.py <command> --help` for details on any command.
"""

import argparse
import json
import os
import sys
import webbrowser
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_FILE = os.path.join(ROOT, "data", "brokers.json")

CONFIG_DIR = os.path.expanduser("~/.config/unlisted")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

FOLLOWUP_DAYS = [30, 45, 90, 120]
STATUSES = ("todo", "sent", "done", "back")

# Consumer deletion statutes by state. Keep in sync with web/app.js.
STATUTES = {
    "CA": ("California Consumer Privacy Act (CCPA/CPRA)", "Cal. Civ. Code § 1798.105", 45),
    "CO": ("Colorado Privacy Act (CPA)", "C.R.S. § 6-1-1306", 45),
    "CT": ("Connecticut Data Privacy Act (CTDPA)", "Conn. Gen. Stat. § 42-518", 45),
    "VA": ("Virginia Consumer Data Protection Act (VCDPA)", "Va. Code § 59.1-577", 45),
    "UT": ("Utah Consumer Privacy Act (UCPA)", "Utah Code § 13-61-202", 45),
    "TX": ("Texas Data Privacy and Security Act (TDPSA)", "Tex. Bus. & Com. Code § 541.051", 45),
    "OR": ("Oregon Consumer Privacy Act (OCPA)", "ORS 646A.578", 45),
    "MT": ("Montana Consumer Data Privacy Act", "Mont. Code Ann. § 30-14-2812", 45),
    "DE": ("Delaware Personal Data Privacy Act", "6 Del. C. § 12D-104", 45),
    "IA": ("Iowa Consumer Data Protection Act", "Iowa Code § 715D.3", 90),
    "NE": ("Nebraska Data Privacy Act", "Neb. Rev. Stat. § 87-1104", 45),
    "NH": ("New Hampshire Data Privacy Act", "RSA 507-H:3", 45),
    "NJ": ("New Jersey Data Privacy Act", "N.J.S.A. 56:8-166.7", 45),
    "MN": ("Minnesota Consumer Data Privacy Act", "Minn. Stat. § 325O.05", 45),
    "MD": ("Maryland Online Data Privacy Act", "Md. Com. Law § 14-4704", 45),
    "IN": ("Indiana Consumer Data Protection Act", "Ind. Code § 24-15-3-1", 45),
    "KY": ("Kentucky Consumer Data Protection Act", "KRS 367.3613", 45),
    "RI": ("Rhode Island Data Transparency and Privacy Protection Act",
           "R.I. Gen. Laws § 6-48.1-4", 45),
}

DROP_NOTICE = """
  ┌───────────────────────────────────────────────────────────────────────┐
  │  You are in California. Use the state's platform instead.             │
  │                                                                       │
  │  DROP (Delete Request and Opt-Out Platform), run by the California     │
  │  Privacy Protection Agency, is free. One verified request compels     │
  │  every broker registered in California to delete your data and stop   │
  │  selling it. Since August 1 2026 they must check it every 45 days,    │
  │  with $200/request/day penalties for non-compliance.                  │
  │                                                                       │
  │      https://privacy.ca.gov/drop/                                     │
  │                                                                       │
  │  Do that first. Come back for brokers that never registered in CA,    │
  │  and to verify listings actually came down.                           │
  └───────────────────────────────────────────────────────────────────────┘
"""


# ---------------------------------------------------------------- plumbing

def die(msg, code=1):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_brokers():
    if not os.path.exists(DATA_FILE):
        die("data/brokers.json not found. Run: python3 scripts/build_dataset.py")
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_json(path, default):
    if not os.path.exists(path):
        return dict(default)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return dict(default)


def save_json(path, obj, private=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    if private:
        try:
            os.chmod(path, 0o600)   # config holds PII; keep it owner-only
        except OSError:
            pass


config = lambda: load_json(CONFIG_FILE, {})
tracker = lambda: load_json(STATE_FILE, {})


def find(brokers, needle):
    """Resolve a domain fragment or name to exactly one broker."""
    n = needle.strip().lower()
    exact = [b for b in brokers if (b.get("domain") or "").lower() == n]
    if exact:
        return exact[0]
    hits = [b for b in brokers
            if n in (b.get("domain") or "").lower() or n in b["name"].lower()]
    if not hits:
        die(f"no broker matches {needle!r}")
    if len(hits) > 1:
        print(f"{needle!r} is ambiguous:", file=sys.stderr)
        for b in hits[:12]:
            print(f"  {b.get('domain') or '-':<38} {b['name']}", file=sys.stderr)
        sys.exit(1)
    return hits[0]


def statute_for(st):
    return STATUTES.get((st or "").upper())


# ----------------------------------------------------------------- letters

def build_letter(broker, cfg, stage="initial"):
    st = (cfg.get("state") or "").upper()
    law = statute_for(st)
    who = " ".join(x for x in [cfg.get("first"), cfg.get("last")] if x) or "[your name]"
    where = ", ".join(x for x in [cfg.get("city"), st] if x)
    days = law[2] if law else 45

    ident = "\n".join(x for x in [
        f"Full name: {who}",
        f"City/State: {where}" if where else None,
        f"Street address: {cfg['address']}" if cfg.get("address") else None,
        f"Contact email: {cfg['email']}" if cfg.get("email") else None,
    ] if x)

    basis = (
        f"I am a resident of {st} and I am exercising my right to deletion under "
        f"the {law[0]}, {law[1]}. You are required to respond substantively within "
        f"{days} days."
        if law else
        "I am asking you to honor this request as a matter of your published privacy "
        "policy. I also ask you to confirm in writing whether you consider yourself "
        "subject to any state consumer privacy statute granting a right to deletion."
    )

    name = broker["name"]

    if stage == "initial":
        subject = f"Request to delete personal information — {who}"
        body = f"""To whom it may concern,

I am writing to request that {name} delete all personal information you hold
about me, and cease selling or sharing that information with third parties.

{basis}

You may identify me with the following:

{ident}

Specifically, I request that you:

1. Delete all personal information you hold about me, including any inferences
   or derived profiles.
2. Direct any service providers, contractors, or third parties to whom you have
   sold, shared, or disclosed my information to do the same.
3. Cease any further sale or sharing of my personal information.
4. Confirm in writing once this has been completed, and tell me the categories
   of information that were deleted.

If you decline this request in whole or in part, please state the specific legal
basis for the denial.

Please do not use the information in this request for any purpose other than
processing it, and do not add my contact details to any marketing list.

Thank you,
{who}
{cfg.get('email', '')}"""

    elif stage == "followup":
        subject = f"Second request — deletion of personal information — {who}"
        body = f"""To whom it may concern,

I am following up on my request that {name} delete all personal information you
hold about me. I have not received confirmation that it was processed.

{basis}

Identifying information, repeated for your convenience:

{ident}

Please confirm in writing that my information has been deleted, or state the
specific legal basis on which you are declining.

Thank you,
{who}
{cfg.get('email', '')}"""

    else:  # final
        subject = f"Final notice before regulatory complaint — {who}"
        escalation = (
            f"The response deadline under the {law[0]} ({law[1]}) has lapsed. If I do "
            f"not receive written confirmation within 10 business days, I intend to "
            f"file a complaint with my state Attorney General"
            + (" and with the California Privacy Protection Agency" if st == "CA" else "")
            + ", and to document this non-response in that complaint."
            if law else
            "If I do not receive a written response within 10 business days, I intend "
            "to file complaints with my state Attorney General and with the Federal "
            "Trade Commission, and to document this non-response in those complaints."
        )
        body = f"""To whom it may concern,

This is my final written request that {name} delete all personal information you
hold about me. I have contacted you multiple times without receiving confirmation
that my request was processed.

{escalation}

Identifying information:

{ident}

Thank you,
{who}
{cfg.get('email', '')}"""

    return subject, body


# ---------------------------------------------------------------- commands

def cmd_init(args):
    cfg = config()
    print("Your details are written to", CONFIG_FILE)
    print("They stay on this machine. Press Enter to keep an existing value.\n")

    def ask(key, label):
        cur = cfg.get(key, "")
        suffix = f" [{cur}]" if cur else ""
        val = input(f"  {label}{suffix}: ").strip()
        if val:
            cfg[key] = val
        elif cur:
            cfg[key] = cur

    ask("first", "First name")
    ask("last", "Last name")
    ask("city", "City")
    ask("state", "State (2-letter)")
    ask("email", "Contact email (an alias is wise)")
    ask("address", "Street address (optional)")

    cfg["state"] = (cfg.get("state") or "").upper()
    save_json(CONFIG_FILE, cfg, private=True)
    print(f"\nSaved to {CONFIG_FILE} (permissions 600).")

    law = statute_for(cfg["state"])
    if cfg["state"] == "CA":
        print(DROP_NOTICE)
    elif law:
        print(f"\nYour letters will cite {law[0]}.")
    else:
        print(f"\nNote: {cfg['state'] or 'your state'} has no consumer deletion statute "
              "in force, so letters will be written as courtesy requests. Many brokers "
              "honor them anyway.")


def cmd_list(args):
    brokers = load_brokers()
    tr = tracker()

    rows = brokers
    if args.category:
        rows = [b for b in rows if b.get("category") == args.category]
    elif not args.all:
        rows = [b for b in rows
                if b.get("category") in ("people-search", "face-search", "phone-directory")]
    if args.status:
        rows = [b for b in rows
                if tr.get(b.get("domain"), {}).get("status", "todo") == args.status]
    rows = rows[:args.top] if args.top else rows

    if not rows:
        print("No brokers match those filters.")
        return

    mark = {"todo": " ", "sent": "→", "done": "✓", "back": "!"}
    print(f"{'':<2} {'#':>4}  {'BROKER':<32} {'DOMAIN':<32} NOTES")
    print("-" * 108)
    for b in rows:
        d = b.get("domain") or ""
        s = tr.get(d, {}).get("status", "todo")
        bits = []
        if b.get("leverage", 0) > 1:
            bits.append(f"clears {b['leverage']}")
        if b.get("verification"):
            bits.append(b["verification"])
        if not b.get("email"):
            bits.append("form only")
        print(f"{mark[s]:<2} {b['rank']:>4}  {b['name'][:32]:<32} {d[:32]:<32} {', '.join(bits)}")

    counts = {s: 0 for s in STATUSES}
    for b in brokers:
        counts[tr.get(b.get("domain"), {}).get("status", "todo")] += 1
    print(f"\n{len(rows)} shown · {counts['todo']} to do, {counts['sent']} submitted, "
          f"{counts['done']} confirmed, {counts['back']} reappeared")


def cmd_open(args):
    b = find(load_brokers(), args.broker)
    url = b.get("opt_out_url")
    if not url:
        die(f"{b['name']} has no recorded opt-out URL"
            + (f"; email {b['email']} instead" if b.get("email") else ""))
    print(f"Opening {b['name']}: {url}")
    if b.get("notes"):
        print(f"  note: {b['notes']}")
    webbrowser.open(url)


def cmd_letter(args):
    b = find(load_brokers(), args.broker)
    cfg = config()
    if not cfg.get("first"):
        die("run `init` first — the letter needs your details")

    subject, body = build_letter(b, cfg, args.stage)
    text = f"To: {b.get('email') or '(no email on file — use the web form)'}\n" \
           f"Subject: {subject}\n\n{body}\n"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            os.chmod(args.out, 0o600)
        except OSError:
            pass
        print(f"Wrote {args.out}")
    else:
        print(text)


def cmd_mark(args):
    b = find(load_brokers(), args.broker)
    if args.status not in STATUSES:
        die(f"status must be one of: {', '.join(STATUSES)}")
    tr = tracker()
    d = b["domain"]
    entry = tr.get(d, {})
    entry["status"] = args.status
    if args.status == "sent":
        entry["date"] = args.date or date.today().isoformat()
    elif args.status == "todo":
        entry.pop("date", None)
    tr[d] = entry
    save_json(STATE_FILE, tr, private=True)
    when = f" ({entry['date']})" if entry.get("date") else ""
    print(f"{b['name']} → {args.status}{when}")


def cmd_due(args):
    brokers = {b["domain"]: b for b in load_brokers() if b.get("domain")}
    tr = tracker()
    today = date.today()
    due, waiting = [], 0

    for d, e in tr.items():
        if e.get("status") != "sent" or not e.get("date"):
            continue
        b = brokers.get(d)
        if not b:
            continue
        try:
            sent = datetime.strptime(e["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        age = (today - sent).days
        stages = [x for x in FOLLOWUP_DAYS if age >= x]
        if stages:
            due.append((age, stages[-1], b))
        else:
            waiting += 1

    if not due:
        print(f"Nothing due. {waiting} request(s) still inside their response window.")
        return

    due.sort(key=lambda x: -x[0])
    print(f"{len(due)} broker(s) need a follow-up:\n")
    for age, stage, b in due:
        if stage >= 120:
            action = "final notice sent already — handle this one by hand"
            cmd = ""
        else:
            nxt = "final" if stage >= 90 else "followup"
            action = f"day-{stage} follow-up due"
            cmd = f"    python3 cli/unlisted.py letter {b['domain']} --stage {nxt}"
        print(f"  {b['name']:<34} {age:>4}d  {action}")
        if cmd:
            print(cmd)
    print(f"\n{waiting} other request(s) still inside their response window.")


def cmd_send(args):
    """Send a letter through the user's own SMTP account.

    Credentials are read from the environment, never stored by this tool:
        UNLISTED_SMTP_HOST, UNLISTED_SMTP_PORT,
        UNLISTED_SMTP_USER, UNLISTED_SMTP_PASS
    """
    import smtplib
    from email.message import EmailMessage

    b = find(load_brokers(), args.broker)
    cfg = config()
    if not cfg.get("first"):
        die("run `init` first")
    if not b.get("email"):
        die(f"{b['name']} has no email on file — use the web form: {b.get('opt_out_url', '')}")

    host = os.environ.get("UNLISTED_SMTP_HOST")
    user = os.environ.get("UNLISTED_SMTP_USER")
    pw = os.environ.get("UNLISTED_SMTP_PASS")
    port = int(os.environ.get("UNLISTED_SMTP_PORT", "587"))
    if not (host and user and pw):
        die("set UNLISTED_SMTP_HOST, UNLISTED_SMTP_USER and UNLISTED_SMTP_PASS first.\n"
            "       These are your own mail credentials and are never written to disk.")

    subject, body = build_letter(b, cfg, args.stage)
    msg = EmailMessage()
    msg["From"] = cfg.get("email") or user
    msg["To"] = b["email"]
    msg["Subject"] = subject
    msg.set_content(body)

    print(f"To:      {b['email']}")
    print(f"From:    {msg['From']}")
    print(f"Subject: {subject}\n")
    if not args.yes and input("Send this? [y/N] ").strip().lower() != "y":
        print("Not sent.")
        return

    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    print("Sent.")

    tr = tracker()
    tr[b["domain"]] = {"status": "sent", "date": date.today().isoformat()}
    save_json(STATE_FILE, tr, private=True)
    print(f"Marked {b['name']} as submitted.")


def cmd_status(args):
    brokers = load_brokers()
    tr = tracker()
    cfg = config()
    counts = {s: 0 for s in STATUSES}
    for b in brokers:
        counts[tr.get(b.get("domain"), {}).get("status", "todo")] += 1

    who = " ".join(x for x in [cfg.get("first"), cfg.get("last")] if x) or "(run init)"
    print(f"Profile:  {who}  {cfg.get('city', '')} {cfg.get('state', '')}")
    print(f"Config:   {CONFIG_FILE}")
    print(f"Tracker:  {STATE_FILE}")
    print(f"Brokers:  {len(brokers)}")
    print(f"          {counts['sent']} submitted, {counts['done']} confirmed, "
          f"{counts['back']} reappeared, {counts['todo']} to do")
    if (cfg.get("state") or "").upper() == "CA":
        print(DROP_NOTICE)


def main():
    p = argparse.ArgumentParser(
        prog="unlisted",
        description="Local-first data broker opt-out helper. Nothing leaves this machine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="set up your details (stored locally)").set_defaults(fn=cmd_init)

    lp = sub.add_parser("list", help="show the prioritized broker worklist")
    lp.add_argument("--top", type=int, default=40, help="how many to show (0 = all)")
    lp.add_argument("--category", help="people-search, face-search, phone-directory, b2b, marketing")
    lp.add_argument("--status", choices=STATUSES)
    lp.add_argument("--all", action="store_true", help="include marketing/upstream brokers")
    lp.set_defaults(fn=cmd_list)

    op = sub.add_parser("open", help="open a broker's opt-out page in your browser")
    op.add_argument("broker")
    op.set_defaults(fn=cmd_open)

    le = sub.add_parser("letter", help="draft a deletion letter")
    le.add_argument("broker")
    le.add_argument("--stage", choices=("initial", "followup", "final"), default="initial")
    le.add_argument("--out", help="write to a file instead of stdout")
    le.set_defaults(fn=cmd_letter)

    mk = sub.add_parser("mark", help="record progress for a broker")
    mk.add_argument("broker")
    mk.add_argument("status", choices=STATUSES)
    mk.add_argument("--date", help="submission date, YYYY-MM-DD (defaults to today)")
    mk.set_defaults(fn=cmd_mark)

    du = sub.add_parser("due", help="show which follow-ups are due now")
    du.set_defaults(fn=cmd_due)

    sd = sub.add_parser("send", help="send a letter via your own SMTP account")
    sd.add_argument("broker")
    sd.add_argument("--stage", choices=("initial", "followup", "final"), default="initial")
    sd.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    sd.set_defaults(fn=cmd_send)

    sub.add_parser("status", help="summary of your progress").set_defaults(fn=cmd_status)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
