import React, { useEffect, useState } from 'react';
import { Card, Badge, Input, FormField, Switch, Button, Alert, PAGE } from '../ui';
import { useToast } from '../context/ToastContext';
import { getAssistantSettings, saveAssistantSettings, getAssistantMetrics, checkAssistant } from '../api/assistant';

const FEATURE_LABELS = {
  brief: 'Pre-session briefs',
  doc_intelligence: 'Document summaries',
  remark_polish: 'Remark polishing',
  census_narrative: 'Census narrative',
};

const th = { textAlign: 'left', padding: '8px 10px', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 };
const td = { padding: '8px 10px', fontSize: 13, color: 'var(--text-body)' };

export default function Settings() {
  const toast = useToast();
  const [agency] = useState('St. Joseph Orphanage');
  const [sync, setSync] = useState(true);
  const [cfg, setCfg] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [saving, setSaving] = useState(false);
  const [check, setCheck] = useState(null);   // { ok, detail }
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    getAssistantSettings().then(setCfg).catch(() => setCfg('error'));
    getAssistantMetrics().then(setMetrics).catch(() => setMetrics(null));
  }, []);

  const save = async (patch) => {
    const next = { ...cfg, ...patch };
    setCfg(next);
    setSaving(true);
    try {
      setCfg(await saveAssistantSettings(next));
      toast.success('Assistant settings saved');
    } catch {
      toast.error('Could not save the assistant settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ ...PAGE, maxWidth: 760 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Card eyebrow="Agency" title="Configuration" padding="22px">
          {/* Display-only. These have never had a backend. */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <FormField label="RCPC" hint="Set by the national office — not editable here yet."><Input value={agency} disabled /></FormField>
            <FormField label="NACC API Endpoint" hint="Managed by the national office.">
              <Input value="https://api.nacc.gov.ph/v1/sync" disabled trailing={<Badge tone="success" size="sm">PROD</Badge>} />
            </FormField>
            <Switch checked={sync} onChange={setSync} disabled label="Auto-sync signed reports to NACC" />
          </div>
        </Card>

        <Card eyebrow="Assistant" title="Local writing assistant" padding="22px">
          {cfg === 'error' && <Alert tone="warning">Could not load the assistant settings.</Alert>}
          {cfg && cfg !== 'error' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <Alert tone="info">
                Drafts are produced by a model running on this machine. Case text
                is never sent to an outside service. Every draft is reviewed and
                approved by a person before it becomes clinical text.
              </Alert>
              <Switch checked={cfg.enabled} disabled={saving}
                      onChange={(v) => save({ enabled: v })}
                      label="Assistant enabled" />
              {Object.entries(FEATURE_LABELS).map(([key, label]) => (
                <Switch key={key} checked={cfg[`feature_${key}`]}
                        disabled={saving || !cfg.enabled}
                        onChange={(v) => save({ [`feature_${key}`]: v })}
                        label={label} />
              ))}
              <FormField label="Runtime URL" hint="The local model runtime. Loopback only.">
                <Input value={cfg.ollama_url} disabled={saving}
                       onChange={(e) => setCfg({ ...cfg, ollama_url: e.target.value })} />
              </FormField>
              <FormField label="Model" hint="Must already be pulled on this machine.">
                <Input value={cfg.model_name} disabled={saving}
                       onChange={(e) => setCfg({ ...cfg, model_name: e.target.value })} />
              </FormField>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <Button variant="ghost" disabled={checking}
                        onClick={async () => {
                          setChecking(true);
                          try { setCheck(await checkAssistant()); }
                          catch { setCheck({ ok: false, detail: 'The check could not be run.' }); }
                          finally { setChecking(false); }
                        }}>
                  {checking ? 'Checking…' : 'Test connection'}
                </Button>
                <Button variant="primary" disabled={saving}
                        onClick={() => save({})}>Save runtime settings</Button>
              </div>
              {check && (
                <Alert tone={check.ok ? 'success' : 'warning'}>{check.detail}</Alert>
              )}
            </div>
          )}
        </Card>

        {metrics && (
          <Card eyebrow="Assistant" title={`Usage — last ${metrics.window_days} days`} padding="22px">
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={th}>Feature</th><th style={th}>Runs</th>
                    <th style={th}>Errors</th><th style={th}>Avg</th>
                    <th style={th}>Kept</th><th style={th}>Edited</th>
                    <th style={th}>Discarded</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.features.map((f) => (
                    <tr key={f.job_type}>
                      <td style={td}>{FEATURE_LABELS[f.job_type] || f.job_type}</td>
                      <td style={td}>{f.runs}</td>
                      <td style={td}>{f.errors}</td>
                      <td style={td}>{f.avg_latency_ms === null ? '—' : `${(f.avg_latency_ms / 1000).toFixed(1)}s`}</td>
                      <td style={td}>{f.accepted}</td>
                      <td style={td}>{f.edited}</td>
                      <td style={td}>{f.discarded}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
