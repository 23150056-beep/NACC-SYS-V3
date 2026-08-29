import React, { createContext, useContext, useMemo, useState } from 'react';

/* The panel's open state used to live inside AssistantPanel, which meant
 * nothing outside it could open the assistant — the quick actions row could
 * only navigate to a route, and the assistant is not one. It is lifted here so
 * a button anywhere can open it, matching how Auth, Toast and Activity are
 * already shared.
 *
 * This is one more door to the same assistant, not a second one: the same
 * endpoint, the same panel, the same stateless session. */
const AssistantCtx = createContext({
  open: false, openAssistant: () => {}, closeAssistant: () => {},
});

export function AssistantProvider({ children }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({
    open,
    openAssistant: () => setOpen(true),
    closeAssistant: () => setOpen(false),
  }), [open]);
  return <AssistantCtx.Provider value={value}>{children}</AssistantCtx.Provider>;
}

export const useAssistant = () => useContext(AssistantCtx);
