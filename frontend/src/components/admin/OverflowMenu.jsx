import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

// The "···" menu that holds every action on a row except its one primary
// (DESIGN_DIRECTION.md §6 Booking row). Items: { label, onClick, destructive,
// disabled }. Destructive items render as quiet red text; callers confirm
// before acting.
export default function OverflowMenu({ items, label = 'More actions' }) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  function openMenu() {
    setRect(buttonRef.current.getBoundingClientRect());
    setOpen(true);
  }

  function close(refocus = true) {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  }

  useEffect(() => {
    if (!open) return undefined;
    menuRef.current?.querySelector('button:not(:disabled)')?.focus();
    function onPointerDown(e) {
      if (menuRef.current?.contains(e.target) || buttonRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onScrollOrResize(e) {
      if (e.type === 'scroll' && menuRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('resize', onScrollOrResize);
    window.addEventListener('scroll', onScrollOrResize, true);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('resize', onScrollOrResize);
      window.removeEventListener('scroll', onScrollOrResize, true);
    };
  }, [open]);

  function handleKey(e) {
    const buttons = [...menuRef.current.querySelectorAll('button:not(:disabled)')];
    const i = buttons.indexOf(document.activeElement);
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      buttons[(i + 1) % buttons.length]?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      buttons[(i - 1 + buttons.length) % buttons.length]?.focus();
    } else if (e.key === 'Tab') {
      close(false);
    }
  }

  const visible = items.filter(Boolean);
  if (visible.length === 0) return null;

  const upward = rect && window.innerHeight - rect.bottom < visible.length * 36 + 24 && rect.top > 160;
  const menuStyle = rect && {
    position: 'fixed',
    right: window.innerWidth - rect.right,
    ...(upward ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="icon-btn"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? close() : openMenu())}
      >
        ···
      </button>
      {open &&
        createPortal(
          <div ref={menuRef} role="menu" className="menu-list" style={menuStyle} onKeyDown={handleKey}>
            {visible.map((item) => (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                disabled={item.disabled}
                className={`menu-item${item.destructive ? ' is-destructive' : ''}`}
                onClick={() => {
                  close(false);
                  item.onClick();
                }}
              >
                {item.label}
              </button>
            ))}
          </div>,
          document.body
        )}
    </>
  );
}
