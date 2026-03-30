import { useState } from 'react';
import { Modal } from './Modal';

export function ScheduleModal({ open, onClose }) {
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [recurring, setRecurring] = useState(false);

  return (
    <Modal open={open} onClose={onClose} title="Schedule message">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <label style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-label)', fontFamily: 'var(--font-label)' }}>
          When
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{
              display: 'block',
              width: '100%',
              marginTop: '4px',
              padding: '8px 12px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
            }}
          />
        </label>
        <label style={{ color: 'var(--text-secondary)', fontSize: 'var(--fs-label)', fontFamily: 'var(--font-label)' }}>
          At
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            style={{
              display: 'block',
              width: '100%',
              marginTop: '4px',
              padding: '8px 12px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
            }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
          <input
            type="checkbox"
            checked={recurring}
            onChange={(e) => setRecurring(e.target.checked)}
          />
          Recurring
        </label>
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '8px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
            }}
          >
            Cancel
          </button>
          <button
            style={{
              padding: '8px 16px',
              background: 'var(--gradient)',
              border: 'none',
              borderRadius: '8px',
              color: 'white',
              cursor: 'pointer',
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: 'var(--fs-label)',
            }}
          >
            Schedule
          </button>
        </div>
      </div>
    </Modal>
  );
}
