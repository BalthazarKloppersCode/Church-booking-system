import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameDay,
  isSameMonth,
  startOfMonth,
  startOfWeek,
} from 'date-fns';
import { formatDayFull } from '../../lib/formatDate';

// Replaces <input type="date"> (DESIGN_DIRECTION.md §6 Fields). The value is
// the same 'YYYY-MM-DD' string a native date input produced, so call sites
// don't change shape. Weeks start on Monday, matching the calendar.

const WEEK = { weekStartsOn: 1 };
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];

function toValue(date) {
  return format(date, 'yyyy-MM-dd');
}

function fromValue(value) {
  return value ? new Date(`${value}T00:00:00`) : null;
}

export default function DatePicker({
  value,
  onChange,
  required,
  disabled,
  size = 'public',
  placeholder = 'Choose a date',
  style,
  id,
  'aria-label': ariaLabel,
}) {
  const selected = fromValue(value);
  const cell = size === 'admin' ? 36 : 44;
  const popWidth = cell * 7 + 24;
  const popHeight = 24 + 44 + 28 + cell * 6;

  const [open, setOpen] = useState(false);
  const [viewMonth, setViewMonth] = useState(() => startOfMonth(selected || new Date()));
  const [focusDate, setFocusDate] = useState(() => selected || new Date());
  const [rect, setRect] = useState(null);
  const buttonRef = useRef(null);
  const popRef = useRef(null);
  // Only pull focus into the grid on open and on keyboard moves — not when the
  // month arrows are clicked, which would steal focus from the arrow itself.
  const focusPending = useRef(false);
  const today = new Date();

  function openPicker() {
    if (disabled) return;
    const base = selected || new Date();
    setViewMonth(startOfMonth(base));
    setFocusDate(base);
    focusPending.current = true;
    setRect(buttonRef.current.getBoundingClientRect());
    setOpen(true);
  }

  function close(refocus = true) {
    setOpen(false);
    if (refocus) buttonRef.current?.focus();
  }

  function pick(date) {
    onChange?.({ target: { value: toValue(date) } });
    close();
  }

  function moveFocus(next) {
    focusPending.current = true;
    setFocusDate(next);
    if (!isSameMonth(next, viewMonth)) setViewMonth(startOfMonth(next));
  }

  function handleGridKey(e) {
    const moves = {
      ArrowLeft: () => addDays(focusDate, -1),
      ArrowRight: () => addDays(focusDate, 1),
      ArrowUp: () => addDays(focusDate, -7),
      ArrowDown: () => addDays(focusDate, 7),
      PageUp: () => addMonths(focusDate, -1),
      PageDown: () => addMonths(focusDate, 1),
    };
    if (moves[e.key]) {
      e.preventDefault();
      moveFocus(moves[e.key]());
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'Tab') {
      close(false);
    }
  }

  useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(e) {
      if (popRef.current?.contains(e.target) || buttonRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onScrollOrResize(e) {
      if (e.type === 'scroll' && popRef.current?.contains(e.target)) return;
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
    if (!open || !focusPending.current) return;
    focusPending.current = false;
    popRef.current?.querySelector(`[data-date="${toValue(focusDate)}"]`)?.focus();
  }, [open, focusDate, viewMonth]);

  const days = eachDayOfInterval({
    start: startOfWeek(startOfMonth(viewMonth), WEEK),
    end: endOfWeek(endOfMonth(viewMonth), WEEK),
  });

  const popStyle = (() => {
    if (!rect) return null;
    const spaceBelow = window.innerHeight - rect.bottom - 8;
    const upward = spaceBelow < popHeight && rect.top > spaceBelow;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - popWidth - 8));
    return {
      position: 'fixed',
      left,
      width: popWidth,
      ...(upward ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
    };
  })();

  return (
    <div className={`select-field select-${size}`} style={style}>
      <button
        ref={buttonRef}
        id={id}
        type="button"
        className={`select-button${selected ? '' : ' is-placeholder'}`}
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => (open ? close() : openPicker())}
      >
        <span className="select-value">{selected ? formatDayFull(selected) : placeholder}</span>
        <svg className="select-chevron" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <rect x="2" y="3" width="12" height="11" rx="2" fill="none" stroke="currentColor" strokeWidth="1.4" />
          <path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      {required && (
        <input
          className="select-required-proxy"
          tabIndex={-1}
          aria-hidden="true"
          required
          value={value || ''}
          onChange={() => {}}
          onFocus={() => buttonRef.current?.focus()}
        />
      )}

      {open &&
        popStyle &&
        createPortal(
          <div ref={popRef} role="dialog" aria-label="Choose a date" className="date-pop" style={popStyle}>
            <div className="date-pop-head">
              <button
                type="button"
                className="date-nav"
                aria-label="Previous month"
                onClick={() => setViewMonth((m) => addMonths(m, -1))}
              >
                ‹
              </button>
              <span className="date-pop-title">{format(viewMonth, 'MMMM yyyy')}</span>
              <button
                type="button"
                className="date-nav"
                aria-label="Next month"
                onClick={() => setViewMonth((m) => addMonths(m, 1))}
              >
                ›
              </button>
            </div>
            <div className="date-grid" style={{ gridTemplateColumns: `repeat(7, ${cell}px)` }} onKeyDown={handleGridKey}>
              {WEEKDAYS.map((d) => (
                <span key={d} className="date-weekday">{d}</span>
              ))}
              {days.map((day) => {
                const isSelected = selected && isSameDay(day, selected);
                const isFocus = isSameDay(day, focusDate);
                return (
                  <button
                    key={toValue(day)}
                    type="button"
                    data-date={toValue(day)}
                    tabIndex={isFocus ? 0 : -1}
                    aria-pressed={!!isSelected}
                    aria-label={format(day, 'EEEE d MMMM yyyy')}
                    className={`date-day${isSelected ? ' is-selected' : ''}${isSameDay(day, today) ? ' is-today' : ''}${
                      isSameMonth(day, viewMonth) ? '' : ' is-outside'
                    }`}
                    style={{ height: cell }}
                    onClick={() => pick(day)}
                  >
                    {format(day, 'd')}
                  </button>
                );
              })}
            </div>
          </div>,
          document.body
        )}
    </div>
  );
}
