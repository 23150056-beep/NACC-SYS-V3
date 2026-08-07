import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '../api/client';
import { useToast } from '../context/ToastContext';
import { Card, StatCard, Button, Badge, Alert, Icon, PAGE } from '../ui';

const RANGES = ['weekly', 'monthly', 'yearly'];
const EMPTY = { total: 0, children: 0, by_case_type: {}, per_psychologist: [], trend: [], terminations_by_reason: {}, pending_pre_assessments: 0, caseload_per_psychologist: [], nacc_service_users: { age_groups: [], case_categories: [] } };

export default function AgencySummary() {
  const toast = useToast();
  const [range, setRange] = useState('monthly');
  const [data, setData] = useState(null);
  const [narrative, setNarrative] = useState(null); // { text, jobId, feedbackSent }
  const [aiBusy, setAiBusy] = useState(false);

  const generateNarrative = async () => {
    setAiBusy(true);
    try {
      const d = data || {};
      const { data: resp } = await api.post('/ai/census-narrative/', {
        stats: {
          range, completed_pre_assessments: d.total, children_seen: d.children,
          pending_pre_assessments: d.pending_pre_assessments,
          by_case_type: d.by_case_type, terminations_by_reason: d.terminations_by_reason,
        },
      });
      setNarrative({ text: resp.draft, jobId: resp.job_id, feedbackSent: false });
    } catch (err) {
      toast.error(err.response?.status === 503
        ? 'AI assistance is switched off or unreachable.'
        : 'Could not generate the narrative.');
    } finally { setAiBusy(false); }
  };

  useEffect(() => {
    api.get(`/reports/summary/?range=${range}`).then((r) => setData(r.data)).catch(() => setData(EMPTY));
  }, [range]);

  const downloadCsv = async () => {
    try {
      const res = await api.get(`/reports/summary/?range=${range}&export=csv`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = `agency-summary-${range}.csv`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { /* ignore */ }
  };

  const d = data || EMPTY;
  const trend = (d.trend || []).map((t) => ({ bucket: t.bucket, count: t.count }));
  const caseMix = Object.entries(d.by_case_type || {});

  return (
    <div style={PAGE} className="racco-print-area">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'inline-flex', gap: 4, background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: 3 }} className="racco-no-print">
          {RANGES.map((r) => (
            <button key={r} onClick={() => setRange(r)} style={{ padding: '6px 16px', borderRadius: 'var(--radius-pill)', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, textTransform: 'capitalize', background: range === r ? 'var(--blue-600)' : 'transparent', color: range === r ? '#fff' : 'var(--text-muted)', transition: 'var(--transition-base)' }}>{r}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10 }} className="racco-no-print">
          <Button variant="secondary" onClick={generateNarrative} disabled={aiBusy || !data} iconLeft={<Icon name={aiBusy ? 'loader' : 'sparkles'} size={17} />}>{aiBusy ? 'Drafting…' : 'AI Narrative'}</Button>
          <Button variant="secondary" onClick={downloadCsv} iconLeft={<Icon name="download" size={17} />}>CSV</Button>
          <Button variant="secondary" onClick={() => window.print()} iconLeft={<Icon name="printer" size={17} />}>Print / Save PDF</Button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: 16, marginBottom: 20 }}>
        <StatCard label="Completed Pre-Assessments" value={d.total} tone="brand" icon={<Icon name="clipboard-check" size={18} />} />
        <StatCard label="Children Seen" value={d.children} tone="success" icon={<Icon name="users" size={18} />} />
        <StatCard label="Pending Pre-Assessments" value={d.pending_pre_assessments} tone="amber" icon={<Icon name="loader" size={18} />} />
      </div>

      {narrative && (
        <Card eyebrow="AI-drafted narrative" title="Monthly summary paragraph" padding="20px" style={{ marginBottom: 20 }}>
          <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.65, margin: '0 0 10px', whiteSpace: 'pre-wrap' }}>{narrative.text}</p>
          <Alert disclaimer title="Draft only.">AI-drafted decision support — review and edit before including it in the agency report.</Alert>
          {!narrative.feedbackSent && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }} className="racco-no-print">
              <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${narrative.jobId}/feedback/`, { outcome: 'accepted' }).catch(() => {}); setNarrative({ ...narrative, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-up" size={15} />}>Useful</Button>
              <Button variant="ghost" onClick={() => { api.post(`/ai/jobs/${narrative.jobId}/feedback/`, { outcome: 'discarded' }).catch(() => {}); setNarrative(null); }} iconLeft={<Icon name="thumbs-down" size={15} />}>Discard</Button>
            </div>
          )}
        </Card>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', gap: 20, marginBottom: 20 }}>
        <Card eyebrow="Sessions over time" title="Trend" padding="20px">
          {trend.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No sessions in this period.</div>
          ) : (
            <div style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer>
                <BarChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="var(--blue-600)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
        <Card eyebrow="Caseload" title="By case type" padding="20px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {caseMix.length === 0 && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>—</div>}
            {caseMix.map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
                <span style={{ fontSize: 13, color: 'var(--text-strong)' }}>{k}</span>
                <span className="racco-mono" style={{ fontWeight: 700, color: 'var(--blue-600)' }}>{v}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card eyebrow="NACC-SAMD reporting" title="Service users (current)" padding="20px" style={{ marginBottom: 20 }}>
        <div className="racco-scroll" style={{ overflowX: 'auto', marginBottom: 14 }}>
          <table style={{ width: '100%', minWidth: 480, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
              {['Age Group', 'Male', 'Female', 'Total'].map((h) => <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {(d.nacc_service_users?.age_groups || []).length === 0
                ? <tr><td colSpan={4} style={{ padding: 16, color: 'var(--text-faint)', fontSize: 13 }}>No active children.</td></tr>
                : d.nacc_service_users.age_groups.map((g) => (
                  <tr key={g.label} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{g.label}</td>
                    <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-body)' }}>{g.male}</td>
                    <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-body)' }}>{g.female}</td>
                    <td className="racco-mono" style={{ padding: '10px 14px', fontSize: 13, fontWeight: 700, color: 'var(--blue-600)' }}>{g.total}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <div className="racco-eyebrow" style={{ fontSize: 10, marginBottom: 8 }}>By case category</div>
        {(d.nacc_service_users?.case_categories || []).length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No active children.</div>
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {d.nacc_service_users.case_categories.map((c) => <Badge key={c.label} tone="neutral">{c.label} · {c.count}</Badge>)}
          </div>
        )}
        <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 14 }}>
          Mirrors the Service Users block of the NACC certification form (NACC-SAMD-GF-000, June 2025).
        </div>
      </Card>

      <Card eyebrow="Case closure" title="Terminations by reason" padding="20px" style={{ marginBottom: 20 }}>
        {Object.keys(d.terminations_by_reason || {}).length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No terminations in this period.</div>
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(d.terminations_by_reason).map(([k, v]) => <Badge key={k} tone="neutral">{k} · {v}</Badge>)}
          </div>
        )}
      </Card>

      <Card eyebrow="Clinical team" title="Per-psychologist activity & caseload" padding="0">
        <div className="racco-scroll" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', minWidth: 560, borderCollapse: 'collapse' }}>
            <thead><tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
              {['Psychologist', 'Sessions (period)', 'Active caseload'].map((h) => <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {(() => {
                const names = [...new Set([
                  ...d.per_psychologist.map((p) => p.name),
                  ...(d.caseload_per_psychologist || []).map((p) => p.name),
                ])];
                if (names.length === 0) return <tr><td colSpan={3} style={{ padding: 16, color: 'var(--text-faint)', fontSize: 13 }}>No activity in this period.</td></tr>;
                return names.map((name) => (
                  <tr key={name} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{name}</td>
                    <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-body)' }}>{d.per_psychologist.find((p) => p.name === name)?.count || 0}</td>
                    <td style={{ padding: '10px 14px', fontSize: 13, color: 'var(--text-body)' }}>{(d.caseload_per_psychologist || []).find((p) => p.name === name)?.caseload || 0}</td>
                  </tr>
                ));
              })()}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
