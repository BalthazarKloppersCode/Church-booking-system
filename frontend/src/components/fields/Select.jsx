import { Children, isValidElement, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

// A fully styled replacement for <select> (DESIGN_DIRECTION.md §6 Fields): same
// call-site shape — value/onChange(e.target.value)/<option> children/required —
// but the closed field and the open list are both ours, not the browser's.
//
// The list renders in a portal with fixed positioning so it isn't clipped by a
// modal's overflow, and a visually hidden native input carries `required` so
// the browser's own form validation still blocks an empty submit.

function readOptions(children) {
  return Children.toArray(children)
    .filter((c) => isValidElement(c) && c.type === 'option')
    .map((c) => ({
      value: c.props.value !== undefined ? String(c.props.value) : String(c.props.children),
      label: c.props.children,
      disabled: !!c.props.disabled,
    }));
}

export default function Select({
  value,
  onChange,
  children,
  required,
  disabled,
  size = 'public',
  placeholder = 'Select…',
  style,
  id,
  'aria-label': ariaLabel,
}) {
  const options = readOptions(children);
  const current = options.find((o) => o.value === String(value ?? ''));
  const showingPlaceholder = !current || current.disabled;

  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [rect, setRect] = useState(null);
  const buttonRef = useRef(null);
  const listRef = useRef(null);
  const listId = useId();

  function openList() {
    if (disabled) return;
    const r = buttonRef.current.getBoundingClientRect();
    setRect(r);
    const idx = options.findIndex((o) => o.value === String(value ?? '') && !o.disabled);
    setHighlight(idx >= 0 ? idx : options.findIndex((o) => !o.disabled));
    setOpen(true);
  }

  function closeList(refocus = true) {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  }

  function choose(option) {
    if (option.disabled) return;
    onChange?.({ target: { value: option.value } });
    closeList();
  }

  function moveHighlight(delta) {
    let i = highlight;
    for (let step = 0; step < options.length; step += 1) {
      i = (i + delta + options.length) % options.length;
      if (!options[i].disabled) {
        setHighlight(i);
        return;
      }
    }
  }

  function handleButtonKey(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openList();
    }
  }

  function handleListKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeList();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      moveHighlight(1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      moveHighlight(-1);
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (highlight >= 0) choose(options[highlight]);
    } else if (e.key === 'Tab') {
      closeList(false);
    }
  }

  useEffect(() => {
    if (!open) return undefined;
    listRef.current?.focus();
    function onPointerDown(e) {
      if (listRef.current?.contains(e.target) || buttonRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onScrollOrResize(e) {
      if (e.type === 'scroll' && listRef.current?.contains(e.target)) return;
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

  useEffect(() => {
    if (!open || highlight < 0) return;
    listRef.current?.children[highlight]?.scrollIntoView({ block: 'nearest' });
  }, [open, highlight]);

  const listMaxHeight = 280;
  const spaceBelow = rect ? window.innerHeight - rect.bottom - 8 : listMaxHeight;
  const openUpward = rect && spaceBelow < 200 && rect.top > spaceBelow;
  const listStyle = rect
    ? {
        position: 'fixed',
        left: rect.left,
        width: rect.width,
        maxHeight: Math.min(listMaxHeight, openUpward ? rect.top - 8 : spaceBelow),
        ...(openUpward ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
      }
    : null;

  return (
    <div className={`select-field select-${size}`} style={style}>
      <button
        ref={buttonRef}
        id={id}
        type="button"
        className={`select-button${showingPlaceholder ? ' is-placeholder' : ''}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-label={ariaLabel}
        onClick={() => (open ? closeList() : openList())}
        onKeyDown={handleButtonKey}
      >
        <span className="select-value">{showingPlaceholder ? current?.label || placeholder : current.label}</span>
        <svg className="select-chevron" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {required && (
        <input
          className="select-required-proxy"
          tabIndex={-1}
          aria-hidden="true"
          required
          value={showingPlaceholder ? '' : String(value)}
          onChange={() => {}}
          onFocus={() => buttonRef.current?.focus()}
        />
      )}

      {open &&
        listStyle &&
        createPortal(
          <ul
            ref={listRef}
            id={listId}
            role="listbox"
            tabIndex={-1}
            className={`select-list select-${size}`}
            style={listStyle}
            onKeyDown={handleListKey}
          >
            {options.map((o, i) => (
              <li
                key={`${o.value}-${i}`}
                role="option"
                aria-selected={o.value === String(value ?? '')}
                aria-disabled={o.disabled || undefined}
                className={`select-option${i === highlight ? ' is-highlighted' : ''}${o.disabled ? ' is-disabled' : ''}${
                  o.value === String(value ?? '') ? ' is-selected' : ''
                }`}
                onMouseEnter={() => !o.disabled && setHighlight(i)}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => choose(o)}
              >
                {o.label}
              </li>
            ))}
          </ul>,
          document.body
        )}
    </div>
  );
}
