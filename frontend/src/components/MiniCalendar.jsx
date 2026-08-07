import React, { useMemo, useState } from 'react';
import { Icon } from '../ui';

const DOW = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const pad = (n) => String(n).padStart(2, '0');
const key = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export default function MiniCalendar({ appointments = [], onOpen }) {
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const marked = useMemo(() => {
    const s = new Set();
    appointments.forEach((a) => { if (a.start) s.add(String(a.start).slice(0, 10)); });
    return s;
  }, [appointments]);

  const cells = useMemo(() => {
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const out = [];
    for (let i = 0; i < first.getDay(); i++) out.push(null);
    const days = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();
    for (let d = 1; d <= days; d++) out.push(new Date(cursor.getFullYear(), cursor.getMonth(), d));
    return out;
  }, [cursor]);

  const today = key(new Date());
  const nav = (n) => setCursor((c) => new Date(c.getFullYear(), c.getMonth() + n, 1));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, cursor: 'pointer' }}
      role="button" tabIndex={0} title="Open the full calendar"
      onClick={onOpen} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(); }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <button aria-label="Previous month" onClick={(e) => { e.stopPropagation(); nav(-1); }}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}><Icon name="chevron-left" size={15} /></button>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 12.5, color: 'var(--text-strong)', display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          {cursor.toLocaleString('en-US', { month: 'long', year: 'numeric' })}
          <Icon name="maximize-2" size={10} style={{ color: 'var(--blue-500)' }} />
        </span>
        <button aria-label="Next month" onClick={(e) => { e.stopPropagation(); nav(1); }}
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', padding: 2 }}><Icon name="chevron-right" size={15} /></button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 1, textAlign: 'center' }}>
        {DOW.map((d) => <span key={d} style={{ fontSize: 9.5, fontWeight: 800, color: 'var(--text-faint)', letterSpacing: '0.04em' }}>{d}</span>)}
        {cells.map((d, i) => d === null ? <span key={`x${i}`} /> : (
          <span key={key(d)} style={{
            position: 'relative', fontSize: 11, fontWeight: key(d) === today ? 800 : 600,
            padding: '2px 0', borderRadius: 'var(--radius-sm)', fontFamily: 'var(--font-mono)',
            background: key(d) === today ? 'var(--blue-600)' : 'transparent',
            color: key(d) === today ? '#fff' : 'var(--text-body)',
          }}>
            {d.getDate()}
            {marked.has(key(d)) && <span style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', bottom: 0, width: 4, height: 4, borderRadius: '50%', background: key(d) === today ? '#fff' : 'var(--blue-500)' }} />}
          </span>
        ))}
      </div>
    </div>
  );
}
