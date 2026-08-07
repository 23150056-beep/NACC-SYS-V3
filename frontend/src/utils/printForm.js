// Print a blank copy of an agency form (e.g. for the guardian or examinee to
// sign on paper). Client-side only — opens a print-friendly window.
// `body` prose renders first ("## " lines become headings); consent forms get
// the document's dual signature blocks (Client/Examinee + Licensed Psychologist).
const esc = (s) => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export function printBlankForm(t) {
  const w = window.open('', '_blank', 'width=800,height=900');
  if (!w) return;
  const bodyHtml = (t.body || '').split('\n').map((line) => {
    const s = line.trim();
    if (!s) return '';
    if (s.startsWith('## ')) return `<h2>${esc(s.slice(3))}</h2>`;
    return `<p>${esc(s)}</p>`;
  }).join('');
  const lines = (t.fields || []).map((f) => {
    if (f.field_type === 'section') return `<h2>${esc(f.label)}</h2>`;
    if (f.field_type === 'yes_no') return `<div class="q">${esc(f.label)} &nbsp;&nbsp; ☐ Yes &nbsp;&nbsp; ☐ No</div>`;
    if (f.field_type === 'choice') return `<div class="q">${esc(f.label)}<br/>${(f.options || []).map((o) => `☐ ${esc(o)}`).join(' &nbsp;&nbsp; ')}</div>`;
    if (f.field_type === 'long_text') return `<div class="q">${esc(f.label)}<div class="box"></div></div>`;
    return `<div class="q">${esc(f.label)}: <span class="line"></span></div>`;
  }).join('');
  const sig = t.form_type === 'consent'
    ? `<div class="sigblock"><div class="sigtitle">CLIENT / EXAMINEE</div>
         <div class="q">Name: <span class="line"></span></div>
         <div class="q">Signature: <span class="line"></span></div>
         <div class="q">Date: <span class="line"></span></div></div>
       <div class="sigblock"><div class="sigtitle">LICENSED PSYCHOLOGIST / EXAMINER</div>
         <div class="q">Name: <span class="line"></span></div>
         <div class="q">License No.: <span class="line"></span></div>
         <div class="q">Signature: <span class="line"></span></div>
         <div class="q">Date: <span class="line"></span></div></div>`
    : `<div class="sig"><div>Signature over printed name</div><div>Date</div></div>`;
  w.document.write(`<!doctype html><html><head><title>${esc(t.title)}</title><style>
    body{font-family:Georgia,serif;max-width:680px;margin:40px auto;color:#111;line-height:1.6}
    h1{font-size:20px;text-align:center} .sub{text-align:center;font-size:12px;color:#555;margin-bottom:28px}
    h2{font-size:14px;margin:22px 0 6px} p{font-size:13px;margin:8px 0;text-align:justify}
    .q{margin:18px 0;font-size:14px} .line{display:inline-block;border-bottom:1px solid #111;min-width:320px}
    .box{border:1px solid #111;height:90px;margin-top:6px}
    .sig{margin-top:48px;display:flex;justify-content:space-between;font-size:13px}
    .sig div{border-top:1px solid #111;padding-top:4px;width:44%;text-align:center}
    .sigblock{margin-top:36px;font-size:13px} .sigtitle{font-weight:bold;margin-bottom:8px}
  </style></head><body>
    <h1>${esc(t.title)}</h1>
    <div class="sub">NACC – Regional Alternative Child Care Office I · Agency-authored form (v${esc(t.version)})</div>
    ${bodyHtml}
    ${lines}
    ${sig}
    <script>window.print();</` + `script></body></html>`);
  w.document.close();
}
