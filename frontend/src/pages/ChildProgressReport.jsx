import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import api from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Card, Button, Badge, Alert, Select, FormField, Icon, iconBtn, PAGE } from '../ui';
import { PA_STATUS_TONES } from '../config/caseData';

const CASE_STATUS_META = {
  pre_assessment: { label: 'Pre-Assessment', tone: 'amber' },
  counseling: { label: 'Counseling', tone: 'brand' },
  terminated: { label: 'Terminated', tone: 'neutral' },
};

const caseRef = (id) => `C-${String(id).padStart(4, '0')}`;
const td = { padding: '10px 14px', fontSize: 13, color: 'var(--text-body)', whiteSpace: 'nowrap' };
const textarea = { width: '100%', resize: 'vertical', padding: '11px 13px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14, lineHeight: 1.55 };
const DISCLAIMER_TEXT = 'AI-drafted decision support, not a diagnosis. The licensed psychologist reviews, edits, and approves all content.';

export default function ChildProgressReport() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();
  const isPsych = user?.role_name === 'Psychologist';
  const [data, setData] = useState(null);
  const [remarkText, setRemarkText] = useState('');
  const [result, setResult] = useState(null); // add-result drawer
  const [plan, setPlan] = useState(null); // treatment plan drawer
  const [instruments, setInstruments] = useState([]);
  const [aiModal, setAiModal] = useState(null); // { title, draft, disclaimer, onConfirm? }
  const [aiBusy, setAiBusy] = useState(false);
  const [latestBrief, setLatestBrief] = useState(null); // { draft, job_id, generated_at }
  const [polishJob, setPolishJob] = useState(null);     // { id, draft } — last polish result
  const [qr, setQr] = useState(null); // { token, url }
  const [surveyTemplates, setSurveyTemplates] = useState([]);
  const [openInterviews, setOpenInterviews] = useState({}); // interview id -> expanded?
  const isStaffOrAdmin = ['Administrator', 'Staff'].includes(user?.role_name);

  const load = () => api.get(`/reports/child/${id}/`).then((r) => setData(r.data)).catch(() => setData('error'));
  useEffect(() => {
    load();
    api.get(`/ai/brief/child/${id}/latest/`).then((r) => setLatestBrief(r.data)).catch(() => {});
    /* eslint-disable-next-line */
  }, [id]);
  useEffect(() => { if (isPsych) api.get('/instruments/').then((r) => setInstruments(r.data)).catch(() => {}); }, [isPsych]);
  useEffect(() => {
    api.get('/form-templates/?type=self_report_gov').then((r) => setSurveyTemplates(r.data)).catch(() => {});
  }, []);

  if (data === 'error') return <div style={PAGE}><Alert tone="danger" icon={<Icon name="alert-triangle" size={18} />}>This report is unavailable.</Alert></div>;
  if (!data) return <div style={PAGE}><div style={{ color: 'var(--text-muted)' }}>Loading report…</div></div>;

  const { child } = data;
  const canWrite = isPsych && String(child.psychologist) === String(user?.id);
  const canAdvance = canWrite || user?.role_name === 'Administrator';
  const activePlan = (data.treatment_plans || []).find((p) => p.status === 'active') || (data.treatment_plans || [])[0];
  const csMeta = CASE_STATUS_META[child.case_status] || CASE_STATUS_META.pre_assessment;

  const advance = async (next) => {
    try {
      await api.post(`/children/${id}/advance-status/`, { case_status: next });
      toast.success(`Case moved to ${CASE_STATUS_META[next].label}`);
      load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not update the case status.'); }
  };

  const createInvite = async () => {
    const tpl = surveyTemplates[0];
    if (!tpl) { toast.error('Create a Self-Report (Government Form) template under Pre-Assessment Instruments first.'); return; }
    try {
      const { data: inv } = await api.post('/opinionnaire-invites/', { child: Number(id), template: tpl.id });
      setQr({ token: inv.token, url: `${window.location.origin}/survey/${inv.token}`, title: tpl.title });
      load();
    } catch (err) { toast.error(JSON.stringify(err.response?.data || 'Could not create the survey link.')); }
  };

  const addRemark = async () => {
    if (!remarkText.trim()) return;
    const saved = remarkText.trim();
    try {
      await api.post('/remarks/', { child: Number(id), text: saved });
      if (polishJob) {
        sendAiFeedback(polishJob.id, saved === polishJob.draft.trim() ? 'accepted' : 'edited');
        setPolishJob(null);
      }
      setRemarkText(''); load(); toast.success('Remark added');
    } catch (err) { toast.error(err.response?.data?.detail || 'Could not add the remark.'); }
  };

  const saveResult = async () => {
    try {
      await api.post('/result-entries/', {
        child: Number(id), instrument: result.instrument || null,
        summary: result.summary, classification: result.classification,
        baseline_category: result.baseline_category || '',
      });
      setResult(null); load(); toast.success('Result entry saved');
    } catch (err) { toast.error(JSON.stringify(err.response?.data || 'Could not save.')); }
  };

  const savePlan = async () => {
    try {
      if (plan.id) await api.patch(`/treatment-plans/${plan.id}/`, { objectives: plan.objectives, interventions: plan.interventions, status: plan.status, review_date: plan.review_date || null });
      else await api.post('/treatment-plans/', { child: Number(id), objectives: plan.objectives, interventions: plan.interventions, review_date: plan.review_date || null });
      setPlan(null); load(); toast.success('Treatment plan saved');
    } catch (err) { toast.error(JSON.stringify(err.response?.data || 'Could not save.')); }
  };

  const download = async (f) => {
    try {
      const res = await api.get(`/report-files/${f.id}/download/`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = f.original_filename || 'report'; a.click();
      URL.revokeObjectURL(url);
    } catch { toast.error('Could not download the file.'); }
  };

  const aiUnavailable = (err) => {
    toast.error(err.response?.status === 503
      ? 'AI assistance is switched off or unreachable — the system works fully without it.'
      : (err.response?.data?.detail || 'AI request failed.'));
  };

  const sendAiFeedback = (jobId, outcome) => {
    if (!jobId) return;
    api.post(`/ai/jobs/${jobId}/feedback/`, { outcome }).catch(() => {});
  };

  const openBrief = (data, regenerated) => {
    setAiModal({
      title: 'AI pre-session brief (draft)', draft: data.draft, disclaimer: data.disclaimer,
      jobId: data.job_id, feedback: true,
      generatedAt: regenerated ? null : data.generated_at,
      onRegenerate: regenerateBrief,
    });
  };

  const regenerateBrief = async () => {
    setAiBusy(true);
    try {
      const { data: d } = await api.post(`/ai/brief/child/${id}/`);
      setLatestBrief({ draft: d.draft, job_id: d.job_id, generated_at: new Date().toISOString() });
      openBrief(d, true);
    } catch (err) { aiUnavailable(err); } finally { setAiBusy(false); }
  };

  const aiBrief = () => {
    if (latestBrief) openBrief({ ...latestBrief, disclaimer: DISCLAIMER_TEXT });
    else regenerateBrief();
  };

  const aiPolish = async () => {
    if (!remarkText.trim()) return;
    setAiBusy(true);
    try {
      const { data: d } = await api.post('/ai/polish-remark/', { text: remarkText.trim() });
      setRemarkText(d.draft);
      setPolishJob({ id: d.job_id, draft: d.draft });
      toast.success('Draft polished — review before saving');
    } catch (err) { aiUnavailable(err); } finally { setAiBusy(false); }
  };

  const aiSummarize = async (f) => {
    setAiBusy(true);
    try {
      const { data: d } = await api.post(`/ai/summarize-report/${f.id}/`);
      setAiModal({
        title: `AI summary draft — ${f.original_filename}`,
        draft: d.draft, disclaimer: d.disclaimer, editable: true,
        onConfirm: async (text) => {
          try {
            await api.post(`/ai/confirm-summary/${f.id}/`, { text });
            toast.success('Summary confirmed');
            setAiModal(null); load();
          } catch (err) { aiUnavailable(err); }
        },
      });
    } catch (err) { aiUnavailable(err); } finally { setAiBusy(false); }
  };

  const aiSummarizeCaseReferral = (f) => {
    setAiBusy(true);
    api.post(`/ai/summarize-case-referral/${f.id}/`)
      .then(({ data: d }) => setAiModal({
        title: `AI summary draft — ${f.original_filename}`,
        draft: d.draft, disclaimer: d.disclaimer, editable: true,
        onConfirm: async (text) => {
          try {
            await api.post(`/ai/confirm-case-referral-summary/${f.id}/`, { text });
            toast.success('Summary confirmed');
            setAiModal(null); load();
          } catch (err) { aiUnavailable(err); }
        },
      }))
      .catch(aiUnavailable).finally(() => setAiBusy(false));
  };

  return (
    <div style={PAGE} className="racco-print-area">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, gap: 10, flexWrap: 'wrap' }} className="racco-no-print">
        <Button variant="ghost" onClick={() => navigate('/reports')} iconLeft={<Icon name="arrow-left" size={17} />}>Back to Results</Button>
        <div style={{ display: 'flex', gap: 10 }}>
          {canWrite && <Button variant="primary" onClick={aiBrief} disabled={aiBusy} iconLeft={<Icon name={aiBusy ? 'loader' : 'sparkles'} size={17} />}>{aiBusy ? 'Working…' : 'AI Pre-Session Brief'}</Button>}
          <Button variant="secondary" onClick={() => window.print()} iconLeft={<Icon name="printer" size={17} />}>Print / Save PDF</Button>
        </div>
      </div>

      {/* Profile header */}
      <Card padding="22px" style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 22, color: 'var(--text-strong)' }}>{child.fullname}</div>
            <div className="racco-mono" style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{caseRef(child.id)} · {child.case_type || '—'}</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
              Psychologist: {child.psychologist_name || '—'} · {[child.barangay, child.municipality, child.province].filter(Boolean).join(', ') || '—'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <Badge tone={csMeta.tone} dot>Case: {csMeta.label}</Badge>
            <Badge tone={PA_STATUS_TONES[child.pre_assessment_status] || 'amber'} dot>Pre-Assessment: {child.pre_assessment_status}</Badge>
            <Badge tone={child.status === 'active' ? 'success' : 'neutral'} dot>{child.status === 'active' ? 'Active' : 'Inactive (Terminated)'}</Badge>
          </div>
        </div>
        {canAdvance && child.status === 'active' && (
          <div style={{ display: 'flex', gap: 10, marginTop: 14, flexWrap: 'wrap' }} className="racco-no-print">
            {child.case_status === 'pre_assessment'
              ? <Button variant="primary" onClick={() => advance('counseling')} iconLeft={<Icon name="chevron-right" size={15} />}>Move to Counseling</Button>
              : <Button variant="secondary" onClick={() => advance('pre_assessment')} iconLeft={<Icon name="arrow-left" size={15} />}>Back to Pre-Assessment</Button>}
          </div>
        )}
        {(child.instruments_used || []).length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
            {child.instruments_used.map((t) => <Badge key={t} tone="brand" size="sm">{t}</Badge>)}
          </div>
        )}
      </Card>

      {/* Pre-assessment log */}
      <Card eyebrow="Clinical workflow" title="Pre-assessment log" padding="0" style={{ marginBottom: 18 }}>
        {data.pre_assessments.length === 0 ? (
          <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)' }}>No pre-assessments yet.</div>
        ) : (
          <div className="racco-scroll" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 640, borderCollapse: 'collapse' }}>
              <thead><tr style={{ background: 'var(--ink-50)', borderBottom: '1px solid var(--border)' }}>
                {['Date', 'Status', 'Consent', 'Interview', 'Instrument Titles', 'Psychologist'].map((h) => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 14px', fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {data.pre_assessments.map((p) => (
                  <tr key={p.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={td}>{p.date}</td>
                    <td style={td}><Badge tone={p.status === 'completed' ? 'success' : 'amber'} size="sm" dot>{p.status.replace('_', ' ')}</Badge></td>
                    <td style={td}>{p.consent ? (p.consent_status || 'linked') : '—'}</td>
                    <td style={td}>{p.interview ? (p.interview_respondent || 'recorded') : '—'}</td>
                    <td style={{ ...td, whiteSpace: 'normal' }}>{(p.instrument_titles || []).join(', ') || '—'}</td>
                    <td style={td}>{p.psychologist_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Clinical interviews — every respondent, incl. secondary "Save & interview another" records */}
      <Card eyebrow="Clinical workflow" title="Clinical interviews" padding="0" style={{ marginBottom: 18 }}>
        {(data.interviews || []).length === 0 ? (
          <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)' }}>
            No clinical interviews recorded yet — they are conducted in the pre-assessment wizard.
          </div>
        ) : (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.interviews.map((iv) => {
              const entries = Object.entries(iv.answers || {}).filter(([, a]) => String(a ?? '').trim() !== '');
              const open = !!openInterviews[iv.id];
              return (
                <div key={iv.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14, background: 'var(--ink-50)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                      <Badge tone="brand" size="sm">{iv.respondent || 'Respondent not recorded'}</Badge>
                      <span style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{iv.template_title || 'Free-form interview'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                      <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>{iv.date} · {iv.interviewer_name || '—'}</span>
                      {entries.length > 0 && (
                        <Button variant="ghost" className="racco-no-print"
                          onClick={() => setOpenInterviews((s) => ({ ...s, [iv.id]: !s[iv.id] }))}
                          iconLeft={<Icon name={open ? 'chevron-up' : 'chevron-down'} size={14} />}>
                          {open ? 'Hide answers' : `Answers (${entries.length})`}
                        </Button>
                      )}
                    </div>
                  </div>
                  {entries.length === 0 && (
                    <div style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 6 }}>No written answers recorded.</div>
                  )}
                  {open && entries.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                      {entries.map(([q, a]) => (
                        <div key={q} style={{ fontSize: 13, lineHeight: 1.5 }}>
                          <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{q}</span>{' '}
                          <span style={{ color: 'var(--text-strong)' }}>— {a}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Child opinionnaire (QR survey) */}
      <Card eyebrow="Child's voice" title="Opinionnaire (QR survey)" padding="20px" style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: (data.opinionnaires || []).length ? 14 : 0 }}>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0, maxWidth: 520 }}>
            The child answers the agency&apos;s self-report opinionnaire on a secondary device via QR code.
            Agency/government forms only — never published instruments.
          </p>
          {(isStaffOrAdmin || canWrite) && child.status === 'active' && (
            <Button variant="primary" onClick={createInvite} iconLeft={<Icon name="qr-code" size={16} />} className="racco-no-print">New QR Survey</Button>
          )}
        </div>
        {(data.opinionnaires || []).length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.opinionnaires.map((o) => (
              <div key={o.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14, background: 'var(--ink-50)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: o.status === 'submitted' ? 8 : 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{o.template_title}</div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Badge tone={o.status === 'submitted' ? 'success' : o.is_open ? 'amber' : 'neutral'} size="sm" dot>
                      {o.status === 'submitted' ? `Answered ${String(o.submitted_at || '').slice(0, 10)}` : o.is_open ? 'Waiting for answers' : 'Expired'}
                    </Badge>
                    {o.is_open && (isStaffOrAdmin || canWrite) && (
                      <Button variant="ghost" onClick={() => setQr({ token: o.token, url: `${window.location.origin}/survey/${o.token}`, title: o.template_title })} iconLeft={<Icon name="qr-code" size={14} />} className="racco-no-print">Show QR</Button>
                    )}
                  </div>
                </div>
                {o.status === 'submitted' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {Object.entries(o.answers || {}).map(([q, a]) => (
                      <div key={q} style={{ fontSize: 13, lineHeight: 1.5 }}>
                        <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>{q}</span>{' '}
                        <span style={{ color: 'var(--text-strong)' }}>— {a}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Case referrals (social worker's side of the split view) */}
      <Card eyebrow="Casework" title="Case referral (social worker)" padding="0" style={{ marginBottom: 18 }}>
        {(data.case_referrals || []).length === 0 ? (
          <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)' }}>
            No case referral uploaded yet. Social workers upload it from Results &amp; Reports.
          </div>
        ) : (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.case_referrals.map((f) => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', background: 'var(--ink-50)' }}>
                <Icon name="folder-heart" size={18} style={{ color: 'var(--amber-500)' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.original_filename}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{f.description || 'Case referral'} · {f.uploaded_by_name || '—'} · {(f.created_at || '').slice(0, 10)}</div>
                  {f.ai_summary && (
                    <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 'var(--radius-md)', background: 'var(--blue-50)', border: '1px solid var(--blue-100)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <Icon name="sparkles" size={12} style={{ color: 'var(--blue-600)' }} />
                        <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--blue-700)' }}>
                          AI summary {f.ai_summary_confirmed ? '· confirmed' : '· draft (unconfirmed)'}
                        </span>
                      </div>
                      <p style={{ fontSize: 12.5, color: 'var(--text-body)', margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{f.ai_summary}</p>
                    </div>
                  )}
                </div>
                {canWrite && f.has_text && (
                  <Button variant="ghost" onClick={() => aiSummarizeCaseReferral(f)} disabled={aiBusy}
                          iconLeft={<Icon name="sparkles" size={15} />} className="racco-no-print">AI summary</Button>
                )}
                <Button variant="ghost" onClick={async () => {
                  try {
                    const res = await api.get(`/case-referrals/${f.id}/download/`, { responseType: 'blob' });
                    const url = URL.createObjectURL(res.data);
                    const a = document.createElement('a'); a.href = url; a.download = f.original_filename || 'case-referral'; a.click();
                    URL.revokeObjectURL(url);
                  } catch { toast.error('Could not download the file.'); }
                }} iconLeft={<Icon name="download" size={15} />} className="racco-no-print">Download</Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Result entries */}
      <Card eyebrow="Findings" title="Result entries (manual)" padding="0" style={{ marginBottom: 18 }}>
        <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'flex-end' }} className="racco-no-print">
          {canWrite && <Button variant="primary" onClick={() => setResult({ instrument: '', summary: '', classification: '', baseline_category: '' })} iconLeft={<Icon name="plus" size={15} />}>Add Result Entry</Button>}
        </div>
        {data.result_entries.length === 0 ? (
          <div style={{ padding: '0 18px 18px', fontSize: 13, color: 'var(--text-muted)' }}>No result entries yet — the psychologist records findings here after paper administration.</div>
        ) : (
          <div style={{ padding: '0 16px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.result_entries.map((r) => (
              <div key={r.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: 14, background: 'var(--ink-50)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)' }}>{r.instrument_title || 'General findings'}</div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    {r.baseline_category && <Badge tone={r.baseline_category === 'Needs Counseling' ? 'amber' : 'success'} size="sm" dot>{r.baseline_category}</Badge>}
                    {r.classification && <Badge tone="brand" size="sm">{r.classification}</Badge>}
                    <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>{r.date}</span>
                  </div>
                </div>
                <p style={{ fontSize: 13.5, color: 'var(--text-body)', margin: 0, lineHeight: 1.6 }}>{r.summary}</p>
                <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 6 }}>Entered by {r.entered_by_name || '—'}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Uploaded reports */}
      <Card eyebrow="Documents" title="Psychological reports" padding="0" style={{ marginBottom: 18 }}>
        {data.reports.length === 0 ? (
          <div style={{ padding: 18, fontSize: 13, color: 'var(--text-muted)' }}>No uploaded reports. Upload from Results &amp; Reports.</div>
        ) : (
          <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {data.reports.map((f) => (
              <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)', background: 'var(--ink-50)' }}>
                <Icon name="file-text" size={18} style={{ color: 'var(--blue-600)' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: 'var(--text-strong)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.original_filename}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>{f.report_type}{f.coverage ? ` · ${f.coverage}` : ''} · {f.author_name || '—'} · {(f.created_at || '').slice(0, 10)}</div>
                  {f.ai_summary && (
                    <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 'var(--radius-md)', background: 'var(--blue-50)', border: '1px solid var(--blue-100)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <Icon name="sparkles" size={12} style={{ color: 'var(--blue-600)' }} />
                        <span style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--blue-700)' }}>
                          AI summary {f.ai_summary_confirmed ? '· confirmed' : '· draft (unconfirmed)'}
                        </span>
                      </div>
                      <p style={{ fontSize: 12.5, color: 'var(--text-body)', margin: 0, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{f.ai_summary}</p>
                    </div>
                  )}
                </div>
                {canWrite && f.has_text && <Button variant="ghost" onClick={() => aiSummarize(f)} disabled={aiBusy} iconLeft={<Icon name="sparkles" size={15} />} className="racco-no-print">AI Summary</Button>}
                <Button variant="ghost" onClick={() => download(f)} iconLeft={<Icon name="download" size={15} />} className="racco-no-print">Download</Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Treatment plan + problems, side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 18, marginBottom: 18 }}>
        <Card eyebrow="Care" title="Treatment plan" padding="20px">
          {activePlan ? (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <Badge tone={activePlan.status === 'active' ? 'success' : 'neutral'} size="sm" dot>{activePlan.status}</Badge>
                {activePlan.review_date && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Review {activePlan.review_date}</span>}
              </div>
              <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Objectives</div>
              <p style={{ fontSize: 13.5, color: 'var(--text-strong)', margin: '4px 0 10px', lineHeight: 1.55 }}>{activePlan.objectives}</p>
              {activePlan.interventions && (<>
                <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Interventions</div>
                <p style={{ fontSize: 13.5, color: 'var(--text-body)', margin: '4px 0 0', lineHeight: 1.55 }}>{activePlan.interventions}</p>
              </>)}
              {canWrite && <div style={{ marginTop: 12 }} className="racco-no-print"><Button variant="secondary" onClick={() => setPlan({ ...activePlan })} iconLeft={<Icon name="pencil" size={15} />}>Edit plan</Button></div>}
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>No treatment plan yet.</div>
              {canWrite && <Button variant="primary" onClick={() => setPlan({ objectives: '', interventions: '', status: 'active', review_date: '' })} iconLeft={<Icon name="plus" size={15} />} className="racco-no-print">Create plan</Button>}
            </div>
          )}
        </Card>

        <Card eyebrow="Watchlist" title="Problems encountered" padding="20px">
          {data.problems.length === 0 ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No problems logged.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.problems.map((p) => (
                <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', borderRadius: 'var(--radius-md)', background: p.resolved ? 'var(--success-50)' : 'var(--ink-50)', border: '1px solid var(--border)' }}>
                  <Icon name={p.resolved ? 'check-circle-2' : 'alert-triangle'} size={15} style={{ color: p.resolved ? 'var(--success-600)' : 'var(--amber-500)' }} />
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--text-strong)', textDecoration: p.resolved ? 'line-through' : 'none', opacity: p.resolved ? 0.7 : 1 }}>{p.description}</span>
                  {p.category && <Badge tone="neutral" size="sm">{p.category}</Badge>}
                  {canWrite && !p.resolved && (
                    <button title="Mark resolved" className="racco-no-print" style={iconBtn('var(--success-600)')}
                      onClick={async () => { try { await api.patch(`/problems/${p.id}/`, { resolved: true }); load(); } catch { toast.error('Could not update.'); } }}>
                      <Icon name="check" size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Remarks log */}
      <Card eyebrow="Progress log" title="Psychological remark notes" padding="20px">
        {canWrite && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: data.remarks.length ? 18 : 0 }} className="racco-no-print">
            <textarea value={remarkText} onChange={(e) => { setRemarkText(e.target.value); if (!e.target.value) setPolishJob(null); }} rows={3} placeholder="Add a dated remark for this child…" style={textarea} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <Button variant="ghost" onClick={aiPolish} disabled={!remarkText.trim() || aiBusy} iconLeft={<Icon name="sparkles" size={15} />}>Polish with AI</Button>
              <Button variant="primary" onClick={addRemark} iconLeft={<Icon name="plus" size={16} />} disabled={!remarkText.trim()}>Add remark</Button>
            </div>
          </div>
        )}
        {data.remarks.length === 0 ? (
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No remarks yet.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {data.remarks.map((n) => (
              <div key={n.id} style={{ borderLeft: '3px solid var(--blue-200)', paddingLeft: 12 }}>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 700 }}>{n.date} · {n.author_name || '—'}</div>
                <p style={{ fontSize: 13.5, lineHeight: 1.6, color: 'var(--text-strong)', margin: '4px 0 0' }}>{n.text}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Alert disclaimer title="Note." style={{ marginTop: 18 }}>All clinical findings are the licensed psychologist&apos;s own professional judgment.</Alert>

      {/* Add-result drawer */}
      {result && (
        <div onClick={() => setResult(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 70 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 440, maxWidth: '92%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>Add result entry</div>
            <FormField label="Instrument (title)">
              <Select value={result.instrument} onChange={(e) => setResult({ ...result, instrument: e.target.value })}>
                <option value="">— General / none —</option>
                {instruments.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
              </Select>
            </FormField>
            <FormField label="Baseline category" hint="Simple post-session verdict for the case tracker.">
              <Select value={result.baseline_category || ''} onChange={(e) => setResult({ ...result, baseline_category: e.target.value })}>
                <option value="">— Not set —</option>
                <option>Needs Counseling</option>
                <option>Good Assessment</option>
              </Select>
            </FormField>
            <FormField label="Findings summary" required>
              <textarea value={result.summary} onChange={(e) => setResult({ ...result, summary: e.target.value })} rows={7} style={textarea} placeholder="Findings in your own words…" />
            </FormField>
            <FormField label="Classification (your own words)">
              <textarea value={result.classification} onChange={(e) => setResult({ ...result, classification: e.target.value })} rows={2} style={textarea} />
            </FormField>
            <Button variant="primary" onClick={saveResult} disabled={!result.summary.trim()} iconLeft={<Icon name="save" size={16} />}>Save entry</Button>
            <div style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>Manual input only — the system never computes scores.</div>
          </div>
        </div>
      )}

      {/* QR modal */}
      {qr && (
        <div onClick={() => setQr(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 90 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 380, maxWidth: '92%', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', padding: 24, textAlign: 'center' }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)', marginBottom: 4 }}>Scan to answer</div>
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginBottom: 16 }}>{qr.title} — hand the second device to the child.</div>
            <div style={{ display: 'inline-block', padding: 14, background: '#fff', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)' }}>
              <QRCodeSVG value={qr.url} size={200} />
            </div>
            <div className="racco-mono" style={{ fontSize: 11, color: 'var(--text-muted)', margin: '12px 0 16px', wordBreak: 'break-all' }}>{qr.url}</div>
            <div style={{ display: 'flex', gap: 10 }}>
              <Button variant="secondary" fullWidth onClick={() => { navigator.clipboard?.writeText(qr.url); toast.success('Link copied'); }}>Copy link</Button>
              <Button variant="primary" fullWidth onClick={() => setQr(null)}>Done</Button>
            </div>
          </div>
        </div>
      )}

      {/* AI draft modal */}
      {aiModal && (
        <div onClick={() => setAiModal(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 90 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 560, maxWidth: '94%', maxHeight: '86vh', overflow: 'hidden', background: 'var(--surface)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xl)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', background: 'var(--ink-50)', display: 'flex', alignItems: 'center', gap: 10 }}>
              <Icon name="sparkles" size={18} style={{ color: 'var(--blue-600)' }} />
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 16, color: 'var(--text-strong)' }}>{aiModal.title}</span>
            </div>
            <div className="racco-scroll" style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
              {aiModal.generatedAt && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12, color: 'var(--text-muted)' }}>
                  <span>Drafted {new Date(aiModal.generatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })} — ready before you clicked.</span>
                  <Button variant="ghost" onClick={() => { setAiModal(null); aiModal.onRegenerate?.(); }} iconLeft={<Icon name="refresh-cw" size={14} />}>Regenerate</Button>
                </div>
              )}
              {aiModal.editable ? (
                <textarea value={aiModal.draft} onChange={(e) => setAiModal({ ...aiModal, draft: e.target.value })} rows={12} style={textarea} />
              ) : (
                <p style={{ fontSize: 13.5, color: 'var(--text-body)', lineHeight: 1.65, margin: 0, whiteSpace: 'pre-wrap' }}>{aiModal.draft}</p>
              )}
              <Alert disclaimer title="Draft only.">{aiModal.disclaimer}</Alert>
            </div>
            <div style={{ padding: 14, borderTop: '1px solid var(--border)', display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setAiModal(null)}>Close</Button>
              {aiModal.feedback && !aiModal.feedbackSent && (
                <>
                  <Button variant="ghost" onClick={() => { sendAiFeedback(aiModal.jobId, 'accepted'); setAiModal({ ...aiModal, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-up" size={15} />}>Useful</Button>
                  <Button variant="ghost" onClick={() => { sendAiFeedback(aiModal.jobId, 'discarded'); setAiModal({ ...aiModal, feedbackSent: true }); }} iconLeft={<Icon name="thumbs-down" size={15} />}>Not useful</Button>
                </>
              )}
              {aiModal.onConfirm && <Button variant="primary" onClick={() => aiModal.onConfirm(aiModal.draft)} iconLeft={<Icon name="check" size={16} />}>Confirm & save</Button>}
            </div>
          </div>
        </div>
      )}

      {/* Treatment plan drawer */}
      {plan && (
        <div onClick={() => setPlan(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(14,19,29,0.32)', display: 'flex', justifyContent: 'flex-end', zIndex: 70 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ width: 440, maxWidth: '92%', height: '100%', background: 'var(--surface)', boxShadow: 'var(--shadow-xl)', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 17, color: 'var(--text-strong)' }}>{plan.id ? 'Edit treatment plan' : 'New treatment plan'}</div>
            <FormField label="Objectives" required>
              <textarea value={plan.objectives} onChange={(e) => setPlan({ ...plan, objectives: e.target.value })} rows={5} style={textarea} />
            </FormField>
            <FormField label="Interventions">
              <textarea value={plan.interventions} onChange={(e) => setPlan({ ...plan, interventions: e.target.value })} rows={5} style={textarea} />
            </FormField>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {plan.id && (
                <FormField label="Status">
                  <Select value={plan.status} onChange={(e) => setPlan({ ...plan, status: e.target.value })}>
                    <option value="active">Active</option><option value="completed">Completed</option><option value="revised">Revised</option>
                  </Select>
                </FormField>
              )}
              <FormField label="Review date">
                <input type="date" value={plan.review_date || ''} onChange={(e) => setPlan({ ...plan, review_date: e.target.value })}
                  style={{ width: '100%', padding: '9px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-strong)', fontFamily: 'var(--font-sans)', fontSize: 14 }} />
              </FormField>
            </div>
            <Button variant="primary" onClick={savePlan} disabled={!plan.objectives.trim()} iconLeft={<Icon name="save" size={16} />}>Save plan</Button>
          </div>
        </div>
      )}
    </div>
  );
}
