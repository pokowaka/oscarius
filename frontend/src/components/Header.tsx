import React from 'react';
import { ChevronLeft, ChevronRight, Activity, Calendar } from 'lucide-react';
import type { Profile, Machine } from '../types';

interface HeaderProps {
  profiles: Profile[];
  selectedProfileId: number | null;
  onSelectProfile: (id: number) => void;
  availableDays: string[];
  selectedDate: string;
  onSelectDate: (date: string) => void;
  activeMachine: Machine | null;
}

export const Header: React.FC<HeaderProps> = ({
  profiles,
  selectedProfileId,
  onSelectProfile,
  availableDays,
  selectedDate,
  onSelectDate,
  activeMachine,
}) => {
  const currentIndex = availableDays.indexOf(selectedDate);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex >= 0 && currentIndex < availableDays.length - 1;

  const handlePrev = () => {
    if (hasPrev) {
      onSelectDate(availableDays[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    if (hasNext) {
      onSelectDate(availableDays[currentIndex + 1]);
    }
  };

  return (
    <header className="navbar">
      <div className="brand-section">
        <div className="brand-logo">
          <Activity size={18} strokeWidth={2.5} />
        </div>
        <div>
          <span className="brand-title">Oscarius</span>
          <span className="brand-tag" style={{ marginLeft: '0.5rem' }}>OSCAR Web</span>
        </div>
      </div>

      <div className="navbar-center">
        <div className="date-navigator">
          <button
            className="nav-icon-btn"
            onClick={handlePrev}
            disabled={!hasPrev}
            title="Previous therapy day"
            aria-label="Previous day"
          >
            <ChevronLeft size={16} />
          </button>

          <div className="date-display">
            <Calendar size={14} color="#94a3b8" />
            <input
              type="date"
              className="date-input"
              value={selectedDate}
              onChange={(e) => {
                if (e.target.value) {
                  onSelectDate(e.target.value);
                }
              }}
              title="Select therapy date"
            />
          </div>

          <button
            className="nav-icon-btn"
            onClick={handleNext}
            disabled={!hasNext}
            title="Next therapy day"
            aria-label="Next day"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="navbar-right">
        {activeMachine && (
          <div className="device-badge" title={`Serial Number: ${activeMachine.serial_number}`}>
            <span>{activeMachine.brand}</span>
            <strong>{activeMachine.model}</strong>
          </div>
        )}

        {profiles.length > 0 && (
          <div className="profile-select-wrapper">
            <select
              className="profile-select"
              value={selectedProfileId || ''}
              onChange={(e) => onSelectProfile(Number(e.target.value))}
              title="Select user profile"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.username}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </header>
  );
};
