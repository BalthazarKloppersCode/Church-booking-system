import { useEffect, useRef } from 'react';

// A panel that slides in from the right for forms too long for a modal
// (DESIGN_DIRECTION.md §8: a twelve-field form in a modal that grows a
// horizontal scrollbar is the container being wrong for the content).
// Scrim click and Escape close it — unless Escape was already used by a
// dropdown or picker inside it (those call preventDefault).
export default function SideSheet({ title, onClose, children, width = 480 }) {
  const panelRef = useRef(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement;
    panelRef.current?.focus();
    return () => previouslyFocused?.focus?.();
  }, []);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'color-mix(in srgb, var(--ink) 34%, transparent)',
      }}
      onClick={onClose}
    >
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        style={{
          position: 'absolute',
          top: 0,
          right: 0,
          bottom: 0,
          width: Math.min(width, window.innerWidth),
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--paper)',
          borderLeft: '1px solid var(--line)',
          boxShadow: 'var(--float)',
          outline: 'none',
        }}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && !e.defaultPrevented) onClose();
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '1px solid var(--line)',
          }}
        >
          <h2 style={{ margin: 0, fontFamily: 'var(--font-body)', fontSize: 16, fontWeight: 600 }}>{title}</h2>
          <button type="button" className="icon-btn" aria-label="Close" onClick={onClose}>✕</button>
        </header>
        <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>{children}</div>
      </aside>
    </div>
  );
}
