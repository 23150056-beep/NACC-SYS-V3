import React from 'react';

/* A render error anywhere below this boundary would otherwise unmount the whole
 * tree and leave a blank white page — indistinguishable, to the person using it,
 * from the system being down. This catches it and says so, with a way out.
 *
 * Class component on purpose: componentDidCatch has no hook equivalent. */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Kept to the console rather than sent anywhere: this trace can contain
    // case data from component props, and no third party is contracted to
    // receive it (see the data-residency section of docs/CLOUD-DEPLOYMENT.md).
    console.error('Unhandled render error:', error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: 'var(--bg, #f8fafc)', color: 'var(--text-body, #1f2937)', fontFamily: 'var(--font-sans, system-ui, sans-serif)' }}>
        <div style={{ maxWidth: 460, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <h1 style={{ margin: 0, fontFamily: 'var(--font-display, inherit)', fontWeight: 800, fontSize: 22 }}>Something went wrong</h1>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>
            This screen could not finish loading. Nothing you had already saved is
            affected — records are stored on the server, not in this page.
          </p>
          <div>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{ marginTop: 6, padding: '10px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', background: 'var(--blue-600, #2542a8)', color: '#fff', fontWeight: 700, fontSize: 14 }}
            >
              Reload the page
            </button>
          </div>
        </div>
      </div>
    );
  }
}
