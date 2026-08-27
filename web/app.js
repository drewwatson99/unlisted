/* Unlisted — data broker opt-out workbench
 *
 * Design rule, enforced throughout: this file makes exactly one network
 * request, for the static broker list. Personal details entered by the user
 * are written to localStorage and read back. They are never transmitted.
 * Letters are handed to the user's own mail client via a mailto: link, so
 * mail is sent by the user, from their own address, as their own agent.
 */

const STORE = 'unlisted.v1';
const STATUSES = ['todo', 'sent', 'done', 'back'];
const STATUS_LABEL = { todo: 'To do', sent: 'Submitted', done: 'Confirmed', back: 'Reappeared' };
const FOLLOWUP_DAYS = [30, 45, 90, 120];

const STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY',
  'LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR',
  'PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'];

/* Consumer privacy statutes with a deletion right, by state. Determines which
 * law a user can actually cite — a CCPA citation from a non-Californian is
 * toothless and gives the broker an easy reason to dismiss the request. */
const STATUTES = {
  CA: { name: 'California Consumer Privacy Act (CCPA/CPRA)', cite: 'Cal. Civ. Code § 1798.105', days: 45 },
  CO: { name: 'Colorado Privacy Act (CPA)', cite: 'C.R.S. § 6-1-1306', days: 45 },
  CT: { name: 'Connecticut Data Privacy Act (CTDPA)', cite: 'Conn. Gen. Stat. § 42-518', days: 45 },
  VA: { name: 'Virginia Consumer Data Protection Act (VCDPA)', cite: 'Va. Code § 59.1-577', days: 45 },
  UT: { name: 'Utah Consumer Privacy Act (UCPA)', cite: 'Utah Code § 13-61-202', days: 45 },
  TX: { name: 'Texas Data Privacy and Security Act (TDPSA)', cite: 'Tex. Bus. & Com. Code § 541.051', days: 45 },
  OR: { name: 'Oregon Consumer Privacy Act (OCPA)', cite: 'ORS 646A.578', days: 45 },
  MT: { name: 'Montana Consumer Data Privacy Act (MTCDPA)', cite: 'Mont. Code Ann. § 30-14-2812', days: 45 },
  DE: { name: 'Delaware Personal Data Privacy Act (DPDPA)', cite: '6 Del. C. § 12D-104', days: 45 },
  IA: { name: 'Iowa Consumer Data Protection Act', cite: 'Iowa Code § 715D.3', days: 90 },
  NE: { name: 'Nebraska Data Privacy Act', cite: 'Neb. Rev. Stat. § 87-1104', days: 45 },
  NH: { name: 'New Hampshire Data Privacy Act', cite: 'RSA 507-H:3', days: 45 },
  NJ: { name: 'New Jersey Data Privacy Act', cite: 'N.J.S.A. 56:8-166.7', days: 45 },
  MN: { name: 'Minnesota Consumer Data Privacy Act', cite: 'Minn. Stat. § 325O.05', days: 45 },
  MD: { name: 'Maryland Online Data Privacy Act', cite: 'Md. Com. Law § 14-4704', days: 45 },
  TN: { name: 'Tennessee Information Protection Act', cite: 'Tenn. Code § 47-18-3king', days: 45 },
  IN: { name: 'Indiana Consumer Data Protection Act', cite: 'Ind. Code § 24-15-3-1', days: 45 },
  KY: { name: 'Kentucky Consumer Data Protection Act', cite: 'KRS 367.3613', days: 45 },
  RI: { name: 'Rhode Island Data Transparency and Privacy Protection Act', cite: 'R.I. Gen. Laws § 6-48.1-4', days: 45 },
};

let BROKERS = [];
let state = load();

/* ---------------------------------------------------------------- storage */

function load() {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* private mode, blocked storage — fall through */ }
  return { profile: {}, records: {} };
}

function save() {
  try {
    localStorage.setItem(STORE, JSON.stringify(state));
  } catch (e) {
    console.warn('Could not persist to localStorage:', e);
  }
}

function rec(domain) {
  if (!state.records[domain]) state.records[domain] = { status: 'todo', date: '', note: '' };
  return state.records[domain];
}

/* ------------------------------------------------------------------ utils */

const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const addDays = (iso, n) => {
  const d = new Date(iso + 'T09:00:00');
  if (isNaN(d)) return null;
  d.setDate(d.getDate() + n);
  return d;
};

const todayISO = () => new Date().toISOString().slice(0, 10);

function profile() {
  return {
    first: (document.getElementById('pFirst').value || '').trim(),
    last: (document.getElementById('pLast').value || '').trim(),
    city: (document.getElementById('pCity').value || '').trim(),
    st: document.getElementById('pState').value || '',
    email: (document.getElementById('pEmail').value || '').trim(),
    addr: (document.getElementById('pAddr').value || '').trim(),
  };
}

/* Builds each broker's own search URL from the user's details so they can
 * check a listing themselves. We deliberately do not fetch these: a human
 * eye is what keeps a same-name stranger's record from being mistaken for
 * the user's, and it sidesteps CAPTCHAs and anti-bot blocking entirely. */
function searchLink(b, p) {
  if (b.search_url && p.first && p.last) {
    return b.search_url
      .replace(/{first}/g, encodeURIComponent(p.first.toLowerCase()))
      .replace(/{last}/g, encodeURIComponent(p.last.toLowerCase()))
      .replace(/{city}/g, encodeURIComponent((p.city || '').toLowerCase()))
      .replace(/{state}/g, encodeURIComponent((p.st || '').toLowerCase()));
  }
  if (b.website && p.first && p.last) {
    return 'https://duckduckgo.com/?q=' + encodeURIComponent(
      `site:${b.domain} "${p.first} ${p.last}"` + (p.city ? ` "${p.city}"` : ''));
  }
  return null;
}

/* ---------------------------------------------------------------- letters */

function buildLetter(b, p, stage) {
  const law = STATUTES[p.st];
  const who = [p.first, p.last].filter(Boolean).join(' ') || '[your full name]';
  const where = [p.city, p.st].filter(Boolean).join(', ');
  const days = law ? law.days : 45;

  const identity = [
    `Full name: ${who}`,
    where ? `City/State: ${where}` : null,
    p.addr ? `Street address: ${p.addr}` : null,
    p.email ? `Contact email: ${p.email}` : null,
  ].filter(Boolean).join('\n');

  const basis = law
    ? `I am a resident of ${p.st} and I am exercising my right to deletion under the ${law.name}, ${law.cite}. You are required to respond substantively within ${days} days.`
    : `I am asking you to honor this request as a matter of your published privacy policy. I am also asking you to confirm in writing whether you consider yourself subject to any state consumer privacy statute that would give me a right to deletion.`;

  if (stage === 'initial') {
    return `Subject: Request to delete personal information — ${who}

To whom it may concern,

I am writing to request that ${b.name} delete all personal information you hold about me, and cease selling or sharing that information with third parties.

${basis}

You may identify me with the following:

${identity}

Specifically, I request that you:

1. Delete all personal information you hold about me, including any inferences or derived profiles.
2. Direct any service providers, contractors, or third parties to whom you have sold, shared, or disclosed my information to do the same.
3. Cease any further sale or sharing of my personal information.
4. Confirm in writing once this has been completed, and tell me the categories of information that were deleted.

If you decline this request in whole or in part, please state the specific legal basis for the denial.

Please do not use the information in this request for any purpose other than processing it, and do not add my contact details to any marketing list.

Thank you,
${who}
${p.email || ''}`;
  }

  if (stage === 'followup') {
    return `Subject: Second request — deletion of personal information — ${who}

To whom it may concern,

I am following up on my request that ${b.name} delete all personal information you hold about me. I have not received confirmation that it was processed.

${basis}

Identifying information, repeated for your convenience:

${identity}

Please confirm in writing that my information has been deleted, or state the specific legal basis on which you are declining.

Thank you,
${who}
${p.email || ''}`;
  }

  return `Subject: Final notice before regulatory complaint — ${who}

To whom it may concern,

This is my final written request that ${b.name} delete all personal information you hold about me. I have now contacted you multiple times without receiving confirmation that my request was processed.

${law
    ? `The response deadline under the ${law.name} (${law.cite}) has lapsed. If I do not receive written confirmation within 10 business days, I intend to file a complaint with my state Attorney General${p.st === 'CA' ? ' and with the California Privacy Protection Agency' : ''}, and to document this non-response in that complaint.`
    : `If I do not receive a written response within 10 business days, I intend to file complaints with my state Attorney General and with the Federal Trade Commission, and to document this non-response in those complaints.`}

Identifying information:

${identity}

Thank you,
${who}
${p.email || ''}`;
}

function openLetter(b, stage) {
  const p = profile();
  if (!p.first || !p.last) {
    alert('Add your first and last name in section 1 first — the letter needs them.');
    return;
  }
  const body = buildLetter(b, p, stage);
  const subject = body.split('\n')[0].replace(/^Subject:\s*/, '');
  const rest = body.split('\n').slice(1).join('\n').trim();

  document.getElementById('dlgTitle').textContent =
    (stage === 'initial' ? 'Deletion request' :
      stage === 'followup' ? 'Follow-up request' : 'Final notice') + ' — ' + b.name;

  const law = STATUTES[p.st];
  document.getElementById('dlgNote').innerHTML = law
    ? `Citing <b>${esc(law.name)}</b>. Review before sending — you are sending this yourself, from your own email, as your own agent.`
    : `<b>${esc(p.st || 'Your state')} has no consumer deletion statute in force</b>, so this is written as a courtesy request rather than a legal demand. Many brokers honor these anyway.`;

  document.getElementById('dlgText').value = rest;
  const mail = document.getElementById('dlgMail');
  if (b.email) {
    mail.href = `mailto:${b.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(rest)}`;
    mail.textContent = `Open in mail app →`;
    mail.removeAttribute('aria-disabled');
    mail.style.display = '';
  } else {
    mail.style.display = 'none';
  }
  document.getElementById('dlg').showModal();
}

/* ------------------------------------------------------------------- .ics */

function icsEscape(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;')
    .replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

function buildICS() {
  const p = profile();
  const lines = [
    'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Unlisted//Opt-Out Follow-ups//EN',
    'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:Data broker follow-ups',
  ];
  let n = 0;

  BROKERS.forEach(b => {
    const r = state.records[b.domain];
    if (!r || r.status !== 'sent' || !r.date) return;

    FOLLOWUP_DAYS.forEach(days => {
      const d = addDays(r.date, days);
      if (!d) return;
      const stamp = d.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';
      const last = days === FOLLOWUP_DAYS[FOLLOWUP_DAYS.length - 1];
      const title = last
        ? `Final notice or handle by hand — ${b.name}`
        : `Day ${days} follow-up — ${b.name}`;
      const desc = last
        ? `No confirmed removal from ${b.name} after ${days} days. Send the final notice, or complete their web form manually. After this point automated follow-up stops.`
        : `Check whether ${b.name} confirmed removal. If not, send the day-${days} follow-up from Unlisted.${b.email ? ' Contact: ' + b.email : ''}`;

      lines.push('BEGIN:VEVENT',
        `UID:unlisted-${b.domain}-${days}-${r.date}@unlisted.local`,
        `DTSTAMP:${stamp}`,
        `DTSTART:${stamp}`,
        `DURATION:PT30M`,
        `SUMMARY:${icsEscape(title)}`,
        `DESCRIPTION:${icsEscape(desc)}`,
        'BEGIN:VALARM', 'TRIGGER:-PT0M', 'ACTION:DISPLAY',
        `DESCRIPTION:${icsEscape(title)}`, 'END:VALARM',
        'END:VEVENT');
      n++;
    });
  });

  lines.push('END:VCALENDAR');
  return { ics: lines.join('\r\n'), count: n };
}

function download(name, text, type) {
  const blob = new Blob([text], { type: type || 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ------------------------------------------------------------------ render */

function visible() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const cat = document.getElementById('fCat').value;
  const st = document.getElementById('fStat').value;
  const limit = parseInt(document.getElementById('fLimit').value, 10);

  let out = BROKERS.filter(b => {
    if (q && !(b.name.toLowerCase().includes(q) || (b.domain || '').includes(q))) return false;
    if (cat === 'priority') {
      if (!['people-search', 'face-search', 'phone-directory'].includes(b.category)) return false;
    } else if (cat !== 'all' && b.category !== cat) return false;
    if (st && (state.records[b.domain]?.status || 'todo') !== st) return false;
    return true;
  });
  if (limit > 0) out = out.slice(0, limit);
  return out;
}

function counts() {
  const c = { todo: 0, sent: 0, done: 0, back: 0 };
  BROKERS.forEach(b => { c[state.records[b.domain]?.status || 'todo']++; });
  document.getElementById('cTodo').textContent = c.todo;
  document.getElementById('cSent').textContent = c.sent;
  document.getElementById('cDone').textContent = c.done;
  document.getElementById('cBack').textContent = c.back;
}

function card(b) {
  const p = profile();
  const r = rec(b.domain);
  const el = document.createElement('article');
  el.className = 'bk';
  el.dataset.s = r.status;

  const tags = [];
  if (b.leverage > 1) tags.push(`<span class="tag lev">clears ${b.leverage} brokers</span>`);
  if (b.category) tags.push(`<span class="tag">${esc(b.category.replace('-', ' '))}</span>`);
  if (b.verification) tags.push(`<span class="tag">verify: ${esc(b.verification)}</span>`);
  if (b.collects_minors) tags.push('<span class="tag hot">collects minors’ data</span>');
  if (b.sold_to_genai) tags.push('<span class="tag hot">sold to AI developers</span>');
  if (b.sold_to_law_enforcement) tags.push('<span class="tag hot">sold to law enforcement</span>');
  if (typeof b.deletion_compliance_rate === 'number' && b.deletion_compliance_rate < 0.75
      && (b.deletion_requests_received || 0) > 500) {
    tags.push(`<span class="tag hot">denies ${Math.round((1 - b.deletion_compliance_rate) * 100)}% of requests</span>`);
  }

  const sLink = searchLink(b, p);
  const stage = r.status === 'sent' && r.date
    && (new Date() - new Date(r.date + 'T00:00:00')) / 864e5 >= 90 ? 'final'
    : r.status === 'sent' ? 'followup' : 'initial';

  el.innerHTML = `
    <div class="bk-top">
      <div class="bk-id">
        <span class="rankbadge mono">#${b.rank}</span>
        <span class="bk-name">${esc(b.name)}</span>
        <span class="bk-dom">${esc(b.domain || '')}</span>
      </div>
      <select class="status" data-v="${r.status}" aria-label="Status for ${esc(b.name)}">
        ${STATUSES.map(s => `<option value="${s}"${s === r.status ? ' selected' : ''}>${STATUS_LABEL[s]}</option>`).join('')}
      </select>
    </div>
    ${tags.length ? `<div class="tags">${tags.join('')}</div>` : ''}
    ${b.notes ? `<div class="note">${esc(b.notes)}</div>` : ''}
    <div class="acts">
      ${sLink ? `<a class="btn" href="${esc(sLink)}" target="_blank" rel="noopener noreferrer">Check listing ↗</a>` : ''}
      ${b.opt_out_url ? `<a class="btn primary" href="${esc(b.opt_out_url)}" target="_blank" rel="noopener noreferrer">Opt-out form ↗</a>` : ''}
      ${b.email ? `<button class="btn" data-letter="${stage}">${stage === 'initial' ? 'Draft letter' : stage === 'followup' ? 'Draft follow-up' : 'Draft final notice'}</button>` : ''}
      ${r.status === 'sent' ? `<span class="stamp">submitted ${esc(r.date || '—')}</span>` : ''}
    </div>`;

  el.querySelector('.status').addEventListener('change', e => {
    r.status = e.target.value;
    if (r.status === 'sent' && !r.date) r.date = todayISO();
    if (r.status === 'todo') r.date = '';
    save(); counts(); render();
  });
  const lb = el.querySelector('[data-letter]');
  if (lb) lb.addEventListener('click', () => openLetter(b, lb.dataset.letter));
  return el;
}

function render() {
  const list = document.getElementById('list');
  const rows = visible();
  list.innerHTML = '';
  rows.forEach(b => list.appendChild(card(b)));
  document.getElementById('empty').hidden = rows.length > 0;
  document.getElementById('shown').textContent = `${rows.length} shown`;
}

/* -------------------------------------------------------------------- init */

function bindProfile() {
  const sel = document.getElementById('pState');
  sel.innerHTML = '<option value="">—</option>' +
    STATES.map(s => `<option value="${s}">${s}</option>`).join('');

  const fields = ['pFirst', 'pLast', 'pCity', 'pState', 'pEmail', 'pAddr'];
  fields.forEach(id => {
    const el = document.getElementById(id);
    if (state.profile[id] != null) el.value = state.profile[id];
    el.addEventListener('input', () => {
      state.profile[id] = el.value;
      save();
      if (id === 'pState') dropVisibility();
      render();
    });
    el.addEventListener('change', () => {
      state.profile[id] = el.value;
      save();
      if (id === 'pState') dropVisibility();
      render();
    });
  });
  dropVisibility();
}

/* The DROP notice is the single most useful thing on this page for a
 * Californian, so it stays prominent for everyone but gets an explicit
 * "this is you" framing once CA is selected. */
function dropVisibility() {
  const st = document.getElementById('pState').value;
  const box = document.getElementById('dropNotice');
  const flag = box.querySelector('.flag');
  if (st === 'CA') {
    flag.textContent = 'You selected California — do this first';
    box.style.borderWidth = '2px';
  } else if (st) {
    flag.textContent = `Not applicable in ${st} — here is what is`;
  } else {
    flag.textContent = 'Read this before you use this tool';
  }
}

function bindTools() {
  document.getElementById('q').addEventListener('input', render);
  ['fCat', 'fStat', 'fLimit'].forEach(id =>
    document.getElementById(id).addEventListener('change', render));

  document.getElementById('dlgX').addEventListener('click',
    () => document.getElementById('dlg').close());
  document.getElementById('dlgCopy').addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(document.getElementById('dlgText').value);
      const b = document.getElementById('dlgCopy');
      b.textContent = 'Copied';
      setTimeout(() => (b.textContent = 'Copy to clipboard'), 1600);
    } catch (e) {
      document.getElementById('dlgText').select();
    }
  });

  document.getElementById('icsBtn').addEventListener('click', () => {
    const { ics, count } = buildICS();
    if (!count) {
      alert('Mark at least one broker as "Submitted" first — follow-ups are scheduled from the date you submitted.');
      return;
    }
    download('unlisted-followups.ics', ics, 'text/calendar');
  });

  document.getElementById('expBtn').addEventListener('click', () => {
    download('unlisted-progress.json', JSON.stringify(state, null, 2), 'application/json');
  });

  document.getElementById('impBtn').addEventListener('click',
    () => document.getElementById('impFile').click());

  document.getElementById('impFile').addEventListener('change', e => {
    const f = e.target.files[0];
    if (!f) return;
    const fr = new FileReader();
    fr.onload = () => {
      try {
        const data = JSON.parse(fr.result);
        if (!data || typeof data !== 'object' || !('records' in data)) throw new Error('bad shape');
        state = { profile: data.profile || {}, records: data.records || {} };
        save();
        location.reload();
      } catch (err) {
        alert('That file could not be read as Unlisted progress data.');
      }
    };
    fr.readAsText(f);
  });

  document.getElementById('clrBtn').addEventListener('click', () => {
    if (!confirm('Erase your details and all tracked progress from this browser? This cannot be undone.')) return;
    state = { profile: {}, records: {} };
    try { localStorage.removeItem(STORE); } catch (e) { /* ignore */ }
    location.reload();
  });
}

async function boot() {
  bindProfile();
  bindTools();
  try {
    const res = await fetch('brokers.json');
    const payload = await res.json();
    BROKERS = payload.brokers || [];
    document.getElementById('rankHint').textContent =
      `${BROKERS.length} brokers, ranked by exposure · data built ${payload.generated}`;
  } catch (e) {
    document.getElementById('rankHint').textContent = 'Could not load broker data.';
    document.getElementById('empty').hidden = false;
    document.getElementById('empty').textContent =
      'Broker data failed to load. If you opened this file directly, serve the folder instead: python3 -m http.server';
    return;
  }
  counts();
  render();
}

boot();
