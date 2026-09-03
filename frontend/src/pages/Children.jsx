import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useActivity } from '../context/ActivityContext';
import { Card, Button, Badge, Input, Select, Avatar, EmptyState, Icon, iconBtn, hoverLift, PAGE } from '../ui';
import { useToast } from '../context/ToastContext';
import { TERMINATION_REASONS } from '../config/caseData';
import ChildForm, { EMPTY } from './children/ChildForm';
import ChildDrawer, { TerminateModal } from './children/ChildDrawer';
import { StatusChip, fmtDay, fmtTime, localDate } from './children/shared';

// Live "who else has this record open" chip — polls the presence heartbeat endpoint.
function usePresence(childId) {
  const [others, setOthers] = useState([]);
  useEffect(() => {
    if (!childId) { setOthers([]); return; }
    let alive = true;
    const beat = () => api.post(`/children/${childId}/presence/`)
      .then((r) => alive && setOthers(r.data.others || [])).catch(() => {});
    beat();
    const t = setInterval(beat, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [childId]);
  return others;
}

function ageFrom(birth) {
  if (!birth) return null;
  const d = new Date(birth);
  if (Number.isNaN(d.getTime())) return null;
  const diff = Date.now() - d.getTime();
  return Math.max(0, Math.floor(diff / (365.25 * 24 * 3600 * 1000)));
}
// Adviser-optimized age groups: Child 1-12, Teen 13-17.
function ageGroup(age) {
  if (age == null) return null;
  if (age <= 12) return 'Child';
  if (age <= 17) return 'Teen';
  return 'Adult';
}
function caseRef(id) {
  return `C-${String(id).padStart(4, '0')}`;
}

// V2 status chip: `Active · Foster Care` / `Archived (Terminated)`.
function ScheduleChip({ appts = [] }) {
  if (appts.length === 0) return <span style={{ color: 'var(--text-faint)' }}>—</span>;
  const today = localDate(new Date());
  const next = appts[0]; // pre-sorted by start
  const isToday = next.start.slice(0, 10) === today;
  return (
    <Badge tone={isToday ? 'amber' : 'neutral'} size="sm" dot>
      {isToday ? `Today · ${fmtTime(next.start)}` : `${fmtDay(next.start)}`}
    </Badge>
  );
}

export default function Children() {
  const { user } = useAuth();
  const { refresh: refreshActivity } = useActivity();
  const toast = useToast();
  const navigate = useNavigate();
  const canManage = ['Administrator', 'Staff'].includes(user?.role_name);
  const isAdmin = user?.role_name === 'Administrator';
  const isPsych = user?.role_name === 'Psychologist';
  const [children, setChildren] = useState([]);
  const [psychologists, setPsychologists] = useState([]);
  const [blocks, setBlocks] = useState([]);
  // childId -> [scheduled appointments in the next 7 days], sorted by start.
  const [apptsByChild, setApptsByChild] = useState({});
  const [searchParams, setSearchParams] = useSearchParams();
  const q = searchParams.get('q') || '';
  const [status, setStatus] = useState('active');
  const [sortMode, setSortMode] = useState('newest');
  const [reasonFilter, setReasonFilter] = useState(''); // Archived tab only (admin/staff)
  const [sel, setSel] = useState(null); // detail drawer record
  const [form, setForm] = useState(null); // add/edit drawer
  const [terminating, setTerminating] = useState(null); // terminate modal record
  const [error, setError] = useState('');
  const others = usePresence(form?.id || sel?.id);
  // The old standalone Archive page folded in here: admin/staff viewing the
  // Archived filter get the termination-detail columns + reopen; psychologists
  // keep the plain roster (they can't reopen, see decision 2026-07-18).
  const showArchiveColumns = canManage && status === 'inactive';

  useEffect(() => { if (status !== 'inactive') setReasonFilter(''); }, [status]);

  const load = useCallback(() => {
    // Include inactive (terminated) cases — the V2 roster shows them with chips.
    api.get('/children/?include_archived=true').then((r) => setChildren(r.data));
    // Active psychologists + current caseload (admin/staff endpoint — also lets Staff assign).
    api.get('/psychologists/').then((r) => setPsychologists(r.data)).catch(() => {});
    // Availability blocks power the assignment-time comparison panel — admin/staff only.
    if (canManage) api.get('/availability/').then((r) => setBlocks(r.data)).catch(() => {});
    // Upcoming (next 7 days) scheduled appointments → roster chips + drawer list.
    // Role-scoped server-side: psychologists get only their own caseload.
    const today = new Date();
    const weekAhead = new Date(today); weekAhead.setDate(today.getDate() + 7);
    api.get(`/appointments/?from=${localDate(today)}&to=${localDate(weekAhead)}`)
      .then((r) => {
        const map = {};
        (r.data || [])
          .filter((a) => a.status === 'scheduled')
          .sort((a, b) => a.start.localeCompare(b.start))
          .forEach((a) => { (map[a.child] ||= []).push(a); });
        setApptsByChild(map);
      })
      .catch(() => setApptsByChild({}));
  }, [canManage]);
  useEffect(() => { load(); }, [load]);

  const setQ = (v) => setSearchParams(v ? { q: v } : {}, { replace: true });

  const rows = useMemo(() => children.map((c) => ({
    ...c,
    age: ageFrom(c.birth_date),
    group: ageGroup(ageFrom(c.birth_date)),
    ref: caseRef(c.id),
  })), [children]);

  const counts = { all: rows.length, active: 0, inactive: 0 };
  rows.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });

  // Adviser: improve alphabetical sorting throughout the system.
  const visible = rows
    .filter((c) => c.fullname.toLowerCase().includes(q.toLowerCase()) || c.ref.toLowerCase().includes(q.toLowerCase()))
    .filter((c) => status === 'all' || c.status === status)
    .filter((c) => !showArchiveColumns || !reasonFilter || c.termination?.reason_category === reasonFilter)
    .sort((a, b) => sortMode === 'newest'
      ? b.id - a.id  // LIFO: newest record first
      : a.fullname.localeCompare(b.fullname, undefined, { sensitivity: 'base' }));

  const STATUS_FILTERS = [
    { key: 'active', label: 'Active' },
    { key: 'inactive', label: 'Archived' },
    { key: 'all', label: 'All' },
  ];
  const dotColor = { active: 'var(--success-500)', inactive: 'var(--text-faint)' };
  const td = { padding: '11px 16px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' };

  const canTerminate = (c) => c.status === 'active'
    && (isAdmin || (isPsych && String(c.psychologist) === String(user?.id)));
  const canEditRecord = (c) => canManage
    || (isPsych && c.status === 'active' && String(c.psychologist) === String(user?.id));

  // Per-user draft key so an unsaved intake typed by one user never leaks
  // into another user's "Add Record" session on a shared workstation.
  const draftKey = `nacc-child-draft:${user?.id ?? 'anon'}`;

  const openCreate = () => {
    setError('');
    let draft = null;
    try { draft = JSON.parse(localStorage.getItem(draftKey) || 'null'); } catch { /* corrupt draft */ }
    const meaningful = draft && Object.entries(draft).some(([k, v]) => k !== 'assignee_sees_history' && v);
    setForm({ ...EMPTY, _draft: meaningful ? draft : null });
  };
  const openEdit = (c) => { setError(''); setForm({ ...EMPTY, ...c, psychologist: c.psychologist || '', _origPsychologist: c.psychologist || '' }); };

  /* /children?openCreate=1 opens the intake form straight away — it is what the
   * dashboard's "Add Record" action links to. The parameter is cleared once
   * used so a refresh, or a back-navigation, does not reopen the form over
   * whatever the person moved on to. */
  const autoOpenCreate = searchParams.get('openCreate') === '1';
  useEffect(() => {
    if (!autoOpenCreate || form) return;
    openCreate();
    const next = new URLSearchParams(searchParams);
    next.delete('openCreate');
    setSearchParams(next, { replace: true });
    // openCreate is stable enough for this one-shot; re-running on every render
    // would fight the user closing the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpenCreate, form]);

  const save = async (e) => {
    e.preventDefault();
    setError('');
    const payload = { ...form, expected_updated_at: form.updated_at };
    delete payload.age; delete payload.group; delete payload.ref;
    delete payload.psychologist_name;
    delete payload._origPsychologist; delete payload.termination; delete payload.photo;
    delete payload.updated_at; delete payload._conflict; delete payload._draft;
    if (!payload.psychologist) payload.psychologist = null;
    if (!payload.birth_date) delete payload.birth_date;
    if (!payload.date_of_admission) delete payload.date_of_admission;
    if (!payload.date_of_placement_to_custodian) delete payload.date_of_placement_to_custodian;
    if (form.id) delete payload.fullname;
    try {
      if (form.id) await api.put(`/children/${form.id}/`, payload);
      else await api.post('/children/', payload);
      try { localStorage.removeItem(draftKey); } catch { /* private browsing */ }
      toast.success(form.id ? 'Record updated' : 'Record added');
      setForm(null);
      load();
      refreshActivity();
    } catch (err) {
      if (err.response?.status === 409) {
        const fresh = err.response.data.current;
        setError('');
        setForm((f) => ({ ...f, _conflict: fresh }));
        toast.error('Someone updated this record while you were editing.');
        return;
      }
      setError(JSON.stringify(err.response?.data || 'Save failed'));
      toast.error('Could not save the record. Please try again.');
    }
  };

  const terminate = async (c, reason, note) => {
    try {
      await api.post(`/children/${c.id}/terminate/`, { reason_category: reason, note });
      toast.success(`${c.fullname}'s case is now inactive`);
      setTerminating(null);
      setSel(null);
      load();
      refreshActivity();
    } catch (err) {
      const d = err.response?.data;
      toast.error(d?.note || d?.reason_category || d?.detail || 'Could not terminate the case.');
    }
  };

  const reopen = async (c) => {
    try {
      await api.post(`/children/${c.id}/reopen/`);
      toast.success(`${c.fullname}'s case is active again — previous records retained`);
      setSel(null);
      load();
      refreshActivity();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not reopen the case.');
    }
  };

  // Duplicate-check warning shortcuts (Add Record form): reuse the existing
  // reopen() for archived matches, or just open the active match's drawer.
  const onDupReopen = async (m) => { await reopen({ id: m.id, fullname: m.fullname }); setForm(null); };
  const onDupOpenExisting = (m) => { setForm(null); const c = rows.find((r) => r.id === m.id); if (c) setSel(c); };

  return (
    <div style={{ ...PAGE, position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ width: 320, maxWidth: '100%' }}>
          <Input placeholder="Search by name or case ID…" value={q} onChange={(e) => setQ(e.target.value)} leading={<Icon name="search" size={16} />} />
        </div>
        {canManage && (
          <Button variant="primary" onClick={openCreate} iconLeft={<Icon name="plus" size={17} />}>Add Record</Button>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <div role="tablist" aria-label="Filter children by status" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {STATUS_FILTERS.map((f) => {
              const on = status === f.key;
              return (
                <button key={f.key} role="tab" aria-selected={on} onClick={() => setStatus(f.key)} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 13px', cursor: 'pointer', borderRadius: 'var(--radius-pill)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12.5, border: `1px solid ${on ? 'var(--blue-500)' : 'var(--border)'}`, background: on ? 'var(--blue-50)' : 'var(--surface)', color: on ? 'var(--blue-700)' : 'var(--text-body)', transition: 'var(--transition-base)' }}>
                  {dotColor[f.key] && <span style={{ width: 7, height: 7, borderRadius: '50%', background: dotColor[f.key] }} />}
                  {f.label}
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600, color: on ? 'var(--blue-600)' : 'var(--text-faint)' }}>{counts[f.key] || 0}</span>
                </button>
              );
            })}
          </div>
          <div style={{ display: 'inline-flex', gap: 4, background: 'var(--ink-50)', border: '1px solid var(--border)', borderRadius: 'var(--radius-pill)', padding: 3 }}>
            {[['newest', 'Newest first'], ['az', 'A–Z']].map(([k, label]) => (
              <button key={k} onClick={() => setSortMode(k)} style={{ padding: '5px 12px', borderRadius: 'var(--radius-pill)', border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12, background: sortMode === k ? 'var(--blue-600)' : 'transparent', color: sortMode === k ? '#fff' : 'var(--text-muted)' }}>{label}</button>
            ))}
          </div>
          {showArchiveColumns && (
            <div style={{ width: 220 }}>
              <Select value={reasonFilter} onChange={(e) => setReasonFilter(e.target.value)} aria-label="Filter by termination reason">
                <option value="">All termination reasons</option>
                {TERMINATION_REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </Select>
            </div>
          )}
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
          Showing <strong style={{ color: 'var(--text-strong)' }}>{visible.length}</strong> of {rows.length} children
        </div>
      </div>

      {canManage && psychologists.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 14, padding: '10px 14px', borderRadius: 'var(--radius-lg)', background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <span className="racco-eyebrow" style={{ fontSize: 10, color: 'var(--text-muted)' }}>Psychologist caseload</span>
          {psychologists.map((p) => (
            <span key={p.id} title={`${p.name}: ${p.caseload} active case${p.caseload === 1 ? '' : 's'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 11px', borderRadius: 'var(--radius-pill)', background: 'var(--ink-50)', border: '1px solid var(--border)', fontSize: 12.5 }}>
              <span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{p.name}</span>
              <span className="racco-mono" style={{ fontWeight: 800, color: p.caseload >= 5 ? 'var(--red-600)' : 'var(--blue-600)' }}>{p.caseload}</span>
            </span>
          ))}
        </div>
      )}

      <Card padding="0">
        {visible.length === 0 ? (
          <EmptyState icon={<Icon name="folder-search" size={24} />} title="No records found" description="Try a different name, case ID, or status filter." />
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: showArchiveColumns ? 860 : 820, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                  {(showArchiveColumns
                    ? ['Child', 'Case Type', 'Terminated On', 'Reason', 'Terminated By', 'Note', 'Actions']
                    : ['Child', 'Gender / Age', 'Psychologist', 'Schedule', 'Status']
                  ).map((h) => (
                    <th key={h} scope="col" style={{ textAlign: 'left', padding: '11px 16px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.id} tabIndex={0} role="button" aria-label={`${c.fullname}, case ${c.ref}. Open details.`}
                    onClick={() => setSel(c)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSel(c); } }}
                    style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer', transition: 'background var(--dur-fast) var(--ease-out)', opacity: c.status === 'inactive' ? 0.72 : 1 }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--blue-50)')} onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                    <td style={{ padding: '11px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 11, minWidth: 0 }}>
                        <Avatar name={c.fullname} tone={showArchiveColumns ? 'neutral' : 'brand'} size="sm" />
                        <div style={{ minWidth: 0, maxWidth: 200 }}>
                          <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--blue-700)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.fullname}</div>
                          <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.ref}</div>
                        </div>
                      </div>
                    </td>
                    {showArchiveColumns ? (
                      <>
                        <td style={{ ...td, whiteSpace: 'nowrap' }}>{c.case_type || '—'}</td>
                        <td style={{ ...td, whiteSpace: 'nowrap' }} className="racco-mono">{c.termination?.date || '—'}</td>
                        <td style={td}>{c.termination?.reason_category
                          ? <Badge tone="amber" size="sm" dot>{c.termination.reason_category}</Badge> : '—'}</td>
                        <td style={{ ...td, whiteSpace: 'nowrap' }}>{c.termination?.terminated_by || '—'}</td>
                        <td style={{ ...td, maxWidth: 260 }}>
                          <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)' }} title={c.termination?.note || ''}>
                            {c.termination?.note || '—'}
                          </span>
                        </td>
                        <td style={{ padding: '11px 16px' }}>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button title="View full record" aria-label={`View ${c.fullname}'s record`} onClick={(e) => { e.stopPropagation(); navigate(`/report/child/${c.id}`); }} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--blue-600)')}><Icon name="eye" size={15} /></button>
                            {isAdmin && (
                              <button title="Reopen case" aria-label={`Reopen ${c.fullname}'s case`}
                                onClick={(e) => { e.stopPropagation(); if (window.confirm('Reopen this case? All previous records and termination history are kept, but the psychologist assignment is cleared — assign one fresh afterwards.')) reopen(c); }}
                                {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })} style={iconBtn('var(--success-600)')}><Icon name="rotate-ccw" size={15} /></button>
                            )}
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td style={td}>{c.gender || '—'} {c.age != null ? `· ${c.age} (${c.group})` : ''}</td>
                        <td style={td}>
                          {c.psychologist_name
                            ? c.psychologist_name
                            : canManage && c.status === 'active'
                              ? (
                                <button title={`Assign a psychologist to ${c.fullname}`} aria-label={`Assign psychologist to ${c.fullname}`}
                                  onClick={(e) => { e.stopPropagation(); openEdit(c); }} {...hoverLift({ lift: -1, shadow: 'var(--shadow-md)' })}
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 'var(--radius-pill)', border: '1px dashed var(--blue-300)', background: 'var(--blue-50)', color: 'var(--blue-700)', fontFamily: 'var(--font-sans)', fontWeight: 700, fontSize: 12, cursor: 'pointer', transition: 'var(--transition-base)' }}>
                                  <Icon name="user-plus" size={13} /> Assign
                                </button>
                              )
                              : '—'}
                        </td>
                        <td style={td}>{c.status === 'active' ? <ScheduleChip appts={apptsByChild[c.id]} /> : <span style={{ color: 'var(--text-faint)' }}>—</span>}</td>
                        <td style={{ padding: '11px 16px' }}><StatusChip child={c} /></td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sel && <ChildDrawer child={sel} upcoming={apptsByChild[sel.id] || []} canEdit={canEditRecord(sel)} canTerminate={canTerminate(sel)} isAdmin={isAdmin} others={others} onEdit={() => { openEdit(sel); setSel(null); }} onTerminate={() => setTerminating(sel)} onReopen={() => { if (window.confirm('Reopen this case? All previous records and termination history are kept, but the psychologist assignment is cleared — assign one fresh afterwards.')) reopen(sel); }} onClose={() => setSel(null)} />}
      {form && <ChildForm form={form} setForm={setForm} draftKey={draftKey} psychologists={psychologists} blocks={blocks} error={error} isPsych={isPsych} isAdmin={isAdmin} others={others} onSubmit={save} onClose={() => setForm(null)} onReopen={onDupReopen} onOpenExisting={onDupOpenExisting} />}
      {terminating && <TerminateModal child={terminating} onConfirm={terminate} onClose={() => setTerminating(null)} />}
    </div>
  );
}

