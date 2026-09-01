import api from './client';

// Sends a test message to the signed-in administrator's own address and
// returns what the mail service actually replied. Every other send in this
// system is fire-and-forget, so this is the only place a failure is visible
// without reading server logs.
export const testEmailDelivery = () =>
  api.post('/email-test/').then((r) => r.data);
