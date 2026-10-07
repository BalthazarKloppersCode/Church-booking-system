import { describe, expect, it } from 'vitest';
import { buildIcs } from './ics';

const NOW = new Date('2026-10-01T12:00:00Z');

describe('buildIcs', () => {
  const ics = buildIcs({
    uid: 'abc123@pinehurst',
    start: '2026-10-14T08:00:00+00:00',
    end: '2026-10-14T10:00:00+00:00',
    summary: 'Wedding, Training Hall',
    location: 'Training Hall; Upper floor',
    description: 'Reference: JGP-1234\nBring chairs',
    now: NOW,
  });

  it('is a CRLF-terminated VCALENDAR with one VEVENT', () => {
    expect(ics.startsWith('BEGIN:VCALENDAR\r\n')).toBe(true);
    expect(ics.endsWith('END:VCALENDAR\r\n')).toBe(true);
    expect(ics.match(/BEGIN:VEVENT/g)).toHaveLength(1);
    expect(ics).not.toMatch(/[^\r]\n/);
  });

  it('writes start/end in UTC regardless of the offset given', () => {
    expect(ics).toContain('DTSTART:20261014T080000Z');
    expect(ics).toContain('DTEND:20261014T100000Z');
    expect(ics).toContain('DTSTAMP:20261001T120000Z');
    expect(buildIcs({ uid: 'x', start: '2026-10-14T10:00:00+02:00', end: '2026-10-14T12:00:00+02:00', summary: 's', now: NOW })).toContain(
      'DTSTART:20261014T080000Z'
    );
  });

  it('escapes commas, semicolons and newlines', () => {
    expect(ics).toContain('SUMMARY:Wedding\\, Training Hall');
    expect(ics).toContain('LOCATION:Training Hall\\; Upper floor');
    expect(ics).toContain('DESCRIPTION:Reference: JGP-1234\\nBring chairs');
  });

  it('omits LOCATION and DESCRIPTION when not given', () => {
    const bare = buildIcs({ uid: 'x', start: '2026-10-14T08:00:00Z', end: '2026-10-14T09:00:00Z', summary: 's', now: NOW });
    expect(bare).not.toContain('LOCATION');
    expect(bare).not.toContain('DESCRIPTION');
  });

  it('folds lines longer than 75 octets', () => {
    const long = buildIcs({ uid: 'x', start: '2026-10-14T08:00:00Z', end: '2026-10-14T09:00:00Z', summary: 'A'.repeat(200), now: NOW });
    for (const line of long.split('\r\n')) {
      expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75);
    }
    // unfolding restores the original text
    expect(long.replace(/\r\n /g, '')).toContain(`SUMMARY:${'A'.repeat(200)}`);
  });
});
