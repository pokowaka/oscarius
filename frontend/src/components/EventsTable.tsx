import React, { useState } from 'react';
import type { RespiratoryEvent } from '../types';

interface EventsTableProps {
  events: RespiratoryEvent[];
  selectedEventId: number | null;
  onSelectEvent: (event: RespiratoryEvent) => void;
}

export const EventsTable: React.FC<EventsTableProps> = ({
  events,
  selectedEventId,
  onSelectEvent,
}) => {
  const [filterType, setFilterType] = useState<string>('ALL');

  const formatTime = (timeMs: number): string => {
    const d = new Date(timeMs);
    return d.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const getTagClass = (code: string): string => {
    const c = code.toLowerCase();
    if (c.includes('obstructive') || c === 'oa') return 'tag-oa';
    if (c.includes('central') || c.includes('clearairway') || c === 'ca') return 'tag-ca';
    if (c.includes('hypopnea') || c === 'h') return 'tag-h';
    if (c.includes('csr') || c.includes('cheyne')) return 'tag-csr';
    if (c.includes('fl') || c.includes('limitation')) return 'tag-fl';
    return 'tag-oa';
  };

  const getEventAbbr = (code: string): string => {
    const c = code.toLowerCase();
    if (c.includes('obstructive') || c === 'oa') return 'OA';
    if (c.includes('central') || c.includes('clearairway') || c === 'ca') return 'CA';
    if (c.includes('hypopnea') || c === 'h') return 'H';
    if (c.includes('csr') || c.includes('cheyne')) return 'CSR';
    if (c.includes('fl') || c.includes('limitation')) return 'FL';
    return code;
  };

  const filteredEvents = events.filter((ev) => {
    const code = ev.channel_code.toLowerCase();
    if (filterType !== 'ALL') {
      if (filterType === 'OA' && !code.includes('obstructive') && code !== 'oa') return false;
      if (filterType === 'CA' && !code.includes('central') && !code.includes('clearairway') && code !== 'ca') return false;
      if (filterType === 'H' && !code.includes('hypopnea') && code !== 'h') return false;
    }
    return true;
  });

  return (
    <div className="events-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="panel-title">Events Log</span>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              backgroundColor: 'var(--bg-surface-elevated)',
              padding: '0.1rem 0.45rem',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
            }}
          >
            {filteredEvents.length}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              backgroundColor: 'var(--bg-main)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
              borderRadius: 'var(--radius-sm)',
              padding: '0.2rem 0.4rem',
              color: 'var(--text-secondary)',
              outline: 'none',
            }}
            title="Filter by event type"
          >
            <option value="ALL">All Events</option>
            <option value="OA">OA (Obstructive)</option>
            <option value="CA">CA (Central)</option>
            <option value="H">H (Hypopnea)</option>
          </select>
        </div>
      </div>

      <div className="events-list">
        {filteredEvents.length === 0 ? (
          <div className="empty-state" style={{ padding: '2rem 1rem' }}>
            <span className="empty-state-title">No events recorded</span>
            <span style={{ fontSize: '0.8rem' }}>No respiratory events match this criteria.</span>
          </div>
        ) : (
          filteredEvents.map((ev) => {
            const isSelected = ev.id === selectedEventId;
            return (
              <div
                key={ev.id}
                className="event-row"
                style={{
                  backgroundColor: isSelected ? 'var(--bg-surface-elevated)' : undefined,
                  borderLeft: isSelected ? '3px solid var(--color-flow)' : '3px solid transparent',
                }}
                onClick={() => onSelectEvent(ev)}
                title="Click to zoom waveform to this event"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <span className={`event-tag ${getTagClass(ev.channel_code)}`}>
                    {getEventAbbr(ev.channel_code)}
                  </span>
                  <span className="event-time">{formatTime(ev.start_time_ms)}</span>
                </div>
                <span className="event-duration">{ev.duration}s</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
