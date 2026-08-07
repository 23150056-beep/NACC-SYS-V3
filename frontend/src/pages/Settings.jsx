import React, { useState, useEffect } from 'react';
import api from '../api/client';
import { Card, Button, Badge, Input, FormField, Switch, Alert, Icon, PAGE } from '../ui';
import { useToast } from '../context/ToastContext';

const FEATURES = [
  ['feature_brief', 'Pre-session brief', 'Summarizes recent records before a session (A1).'],
  ['feature_doc_intelligence', 'Report document intelligence', 'Drafts key findings from uploaded reports (A2).'],
  ['feature_remark_polish', 'Remark polishing', 'Rewrites shorthand remarks as clinical prose (A3).'],
  ['feature_census_narrative', 'Census narrative', 'Drafts the monthly agency summary paragraph (A5).'],
];

export default function Settings() {
  const toast = useToast();
  const [agency, setAgency] = useState('St. Joseph Orphanage');
  const [sync, setSync] = useState(true);
  const [ai, setAi] = useState(null);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    api.get('/ai/settings/').then((r) => setAi(r.data)).catch(() => {});
    api.get('/ai/metrics/').then((r) => setMetrics(r.data)).catch(() => {});
  }, []);

  const saveConfig = async () => {
    try {
      if (ai) {
        const { updated_at, ...payload } = ai;
        await api.patch('/ai/settings/', payload);
      }
      toast.success('Settings saved');
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('Only an Administrator can change these settings.');
      } else {
        // DRF validation errors come back keyed by field name (e.g.
        // { ollama_url: ["AI must run on this machine..."] }) — surface the
        // specific message instead of a generic one when present.
        const fieldError = err.response?.data?.ollama_url?.[0];
        toast.error(fieldError || 'Could not save settings. Please try again.');
      }
    }
  };

  return (
    <div style={{ ...PAGE, maxWidth: 760 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Card eyebrow="Agency" title="Configuration" padding="22px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <FormField label="RCPC"><Input value={agency} onChange={(e) => setAgency(e.target.value)} /></FormField>
            <FormField label="NACC API Endpoint" hint="Managed by the national office.">
              <Input value="https://api.nacc.gov.ph/v1/sync" disabled trailing={<Badge tone="success" size="sm">PROD</Badge>} />
            </FormField>
            <Switch checked={sync} onChange={setSync} label="Auto-sync signed reports to NACC" />
          </div>
        </Card>

        <Card eyebrow="AI Assistance" title="Local AI Layer (Ollama)" padding="22px">
          {!ai ? (
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Alert disclaimer title="Private by design.">
                All AI runs on a local model — child data never leaves this machine. Every output is a
                draft the psychologist confirms; the system is fully functional with AI off.
              </Alert>
              <Switch checked={ai.enabled} onChange={(v) => setAi({ ...ai, enabled: v })} label="Enable AI assistance (master switch)" />
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <FormField label="Ollama endpoint" hint="Must point to this machine (localhost) — child data never leaves RACCO I's hardware.">
                  <Input value={ai.ollama_url} onChange={(e) => setAi({ ...ai, ollama_url: e.target.value })} disabled={!ai.enabled} />
                </FormField>
                <FormField label="Model">
                  <Input value={ai.model_name} onChange={(e) => setAi({ ...ai, model_name: e.target.value })} disabled={!ai.enabled} placeholder="qwen2.5:7b-instruct" />
                </FormField>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, opacity: ai.enabled ? 1 : 0.5 }}>
                {FEATURES.map(([key, label, hint]) => (
                  <div key={key} style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, padding: '10px 12px', borderRadius: 'var(--radius-md)', background: 'var(--ink-50)', border: '1px solid var(--border)' }}>
                    <div>
                      <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--text-strong)' }}>{label}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{hint}</div>
                    </div>
                    <Switch checked={ai[key]} onChange={(v) => setAi({ ...ai, [key]: v })} disabled={!ai.enabled} />
                  </div>
                ))}
              </div>
              {metrics && (
                <div style={{ marginTop: 18 }}>
                  <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 14, color: 'var(--text-strong)', marginBottom: 8 }}>Usage (last 30 days)</div>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                      <thead>
                        <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                          {['Feature', 'Runs', 'Success', 'Avg latency', 'Accepted', 'Edited', 'Discarded'].map((h) => (
                            <th key={h} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(metrics).map(([k, m]) => {
                          const d = m.last_30_days;
                          return (
                            <tr key={k}>
                              <td style={{ padding: '6px 8px' }}>{m.label}</td>
                              <td style={{ padding: '6px 8px' }}>{d.runs}</td>
                              <td style={{ padding: '6px 8px' }}>{d.runs ? Math.round((d.ok / d.runs) * 100) + '%' : '—'}</td>
                              <td style={{ padding: '6px 8px' }}>{d.avg_latency_ms != null ? (d.avg_latency_ms / 1000).toFixed(1) + ' s' : '—'}</td>
                              <td style={{ padding: '6px 8px' }}>{d.outcomes.accepted}</td>
                              <td style={{ padding: '6px 8px' }}>{d.outcomes.edited}</td>
                              <td style={{ padding: '6px 8px' }}>{d.outcomes.discarded}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 6 }}>Acceptance is recorded when a draft is confirmed, inserted, or rated by the psychologist.</p>
                </div>
              )}
            </div>
          )}
        </Card>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button variant="primary" onClick={saveConfig} iconLeft={<Icon name="save" size={17} />}>Save Configuration</Button>
        </div>
      </div>
    </div>
  );
}
