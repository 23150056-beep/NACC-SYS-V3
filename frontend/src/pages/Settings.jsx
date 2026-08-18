import React, { useState } from 'react';
import { Card, Badge, Input, FormField, Switch, PAGE } from '../ui';

export default function Settings() {
  const [agency] = useState('St. Joseph Orphanage');
  const [sync, setSync] = useState(true);

  return (
    <div style={{ ...PAGE, maxWidth: 760 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <Card eyebrow="Agency" title="Configuration" padding="22px">
          {/* Display-only. These have never had a backend — the AI settings were
              the only thing this screen persisted, and the AI layer is gone. */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <FormField label="RCPC" hint="Set by the national office — not editable here yet."><Input value={agency} disabled /></FormField>
            <FormField label="NACC API Endpoint" hint="Managed by the national office.">
              <Input value="https://api.nacc.gov.ph/v1/sync" disabled trailing={<Badge tone="success" size="sm">PROD</Badge>} />
            </FormField>
            <Switch checked={sync} onChange={setSync} disabled label="Auto-sync signed reports to NACC" />
          </div>
        </Card>
      </div>
    </div>
  );
}
