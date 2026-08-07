import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Card, Input, EmptyState, Icon, PAGE } from '../ui';

export default function Monitoring() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');

  useEffect(() => {
    api.get('/reports/monitoring/').then((r) => setRows(r.data)).catch(() => {});
  }, []);

  const visible = useMemo(() => rows
    .filter((r) => (r.child_name || '').toLowerCase().includes(q.toLowerCase())
      || (r.case_ref || '').toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => (a.child_name || '').localeCompare(b.child_name || '', undefined, { sensitivity: 'base' })),
    [rows, q]);

  const td = { padding: '11px 16px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap' };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ width: 340, maxWidth: '100%' }}>
          <Input placeholder="Search by child name or case ID…" value={q} onChange={(e) => setQ(e.target.value)} leading={<Icon name="search" size={16} />} />
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
          Showing <strong style={{ color: 'var(--text-strong)' }}>{visible.length}</strong> of {rows.length} children
        </div>
      </div>

      <Card padding="0">
        {visible.length === 0 ? (
          <EmptyState icon={<Icon name="folder-search" size={24} />} title="No children to monitor" description="Try a different name or case ID." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 820, borderCollapse: 'collapse', fontFamily: 'var(--font-sans)' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {['Child', 'Case Status', 'Psychologist', 'Pre-Assessment', 'Latest Classification', 'Last Activity', 'Next Session'].map((h) => (
                    <th key={h} scope="col" style={{ textAlign: 'left', padding: '11px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const open = () => navigate(`/report/child/${r.child_id}`);
                  return (
                    <tr key={r.child_id} tabIndex={0} role="button" aria-label={`Open ${r.child_name}'s progress report`}
                      onClick={open}
                      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }}
                      style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer', transition: 'background var(--dur-fast) var(--ease-out)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                      <td style={{ padding: '11px 16px' }}>
                        <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--blue-700)', whiteSpace: 'nowrap' }}>{r.child_name}</div>
                        <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.case_ref}</div>
                      </td>
                      <td style={td}>{r.case_status === 'counseling' ? 'Counseling' : r.case_status === 'terminated' ? 'Terminated' : 'Pre-Assessment'}{r.case_type ? ` · ${r.case_type}` : ''}</td>
                      <td style={td}>{r.psychologist_name || '—'}</td>
                      <td style={td}>{r.pre_assessment_status}</td>
                      <td style={td}>{r.latest_classification || '—'}</td>
                      <td style={td}>{r.last_activity || '—'}</td>
                      <td style={td}>{r.next_session || '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
