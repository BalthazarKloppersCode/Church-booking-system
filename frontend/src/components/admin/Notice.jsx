// A dismissible confirmation line shown above a list or calendar.
export default function Notice({ children, onDismiss }) {
  return (
    <div
      role="status"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        margin: '0 0 14px',
        padding: '9px 12px',
        fontSize: 14,
        color: 'var(--ok)',
        background: 'var(--ok-bg)',
        border: '1px solid var(--ok-bd)',
        borderRadius: 8,
      }}
    >
      <span>{children}</span>
      <button type="button" className="icon-btn" aria-label="Dismiss" onClick={onDismiss}>✕</button>
    </div>
  );
}
