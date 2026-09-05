import React from 'react';
import { Clock, AlertCircle, CheckCircle2, Moon } from 'lucide-react';
import type { DailySummary } from '../types';

interface DailyScorecardProps {
  summary: DailySummary | null;
}

export const DailyScorecard: React.FC<DailyScorecardProps> = ({ summary }) => {
  if (!summary) {
    return (
      <div className="scorecard-grid">
        <div className="scorecard-item">
          <span className="scorecard-label">Therapy Time</span>
          <div className="scorecard-value-row">
            <span className="scorecard-value" style={{ color: '#64748b' }}>--:--</span>
          </div>
        </div>
        <div className="scorecard-item">
          <span className="scorecard-label">Total AHI</span>
          <div className="scorecard-value-row">
            <span className="scorecard-value" style={{ color: '#64748b' }}>--</span>
          </div>
        </div>
      </div>
    );
  }

  // Format hours and minutes
  const totalHours = summary.total_hours;
  const hours = Math.floor(totalHours);
  const minutes = Math.round((totalHours - hours) * 60);
  const durationText = `${hours}h ${minutes.toString().padStart(2, '0')}m`;

  const isCompliant = totalHours >= 4.0;

  // AHI clinical classification
  const ahi = summary.ahi;
  let ahiStatusClass = 'status-normal';
  let ahiLabel = 'Normal';
  if (ahi >= 30) {
    ahiStatusClass = 'status-severe';
    ahiLabel = 'Severe';
  } else if (ahi >= 15) {
    ahiStatusClass = 'status-moderate';
    ahiLabel = 'Moderate';
  } else if (ahi >= 5) {
    ahiStatusClass = 'status-mild';
    ahiLabel = 'Mild';
  }

  const hiCount = Math.max(
    0,
    summary.all_apnea_count - (summary.obstructive_hypopnea_count + summary.central_hypopnea_count)
  );
  const hi = totalHours > 0 ? (hiCount / totalHours).toFixed(2) : '0.00';

  return (
    <div className="scorecard-grid">
      {/* Therapy Usage & Compliance */}
      <div className="scorecard-item">
        <div className="scorecard-header">
          <span className="scorecard-label">Usage Duration</span>
          <Clock size={14} color="#94a3b8" />
        </div>
        <div className="scorecard-value-row">
          <span className="scorecard-value">{durationText}</span>
        </div>
        <div>
          {isCompliant ? (
            <span className="compliance-badge compliance-pass">
              <CheckCircle2 size={12} /> Compliant (&ge;4h)
            </span>
          ) : (
            <span className="compliance-badge compliance-fail">
              <AlertCircle size={12} /> Non-compliant (&lt;4h)
            </span>
          )}
        </div>
      </div>

      {/* AHI */}
      <div className="scorecard-item">
        <div className="scorecard-header">
          <span className="scorecard-label">Total AHI</span>
          <Moon size={14} color="#94a3b8" />
        </div>
        <div className="scorecard-value-row">
          <span className="scorecard-value">{ahi.toFixed(2)}</span>
          <span className="scorecard-unit">events/hr</span>
        </div>
        <div>
          <span className={`status-indicator ${ahiStatusClass}`}>
            {ahiLabel} (&lt;5 normal)
          </span>
        </div>
      </div>

      {/* Obstructive Index */}
      <div className="scorecard-item">
        <div className="scorecard-header">
          <span className="scorecard-label">Obstructive (OAI)</span>
          <span className="scorecard-unit">{summary.obstructive_hypopnea_count} events</span>
        </div>
        <div className="scorecard-value-row">
          <span className="scorecard-value" style={{ color: 'var(--color-oa)' }}>
            {summary.oahi.toFixed(2)}
          </span>
          <span className="scorecard-unit">/hr</span>
        </div>
      </div>

      {/* Central Index */}
      <div className="scorecard-item">
        <div className="scorecard-header">
          <span className="scorecard-label">Central (CAI)</span>
          <span className="scorecard-unit">{summary.central_hypopnea_count} events</span>
        </div>
        <div className="scorecard-value-row">
          <span className="scorecard-value" style={{ color: 'var(--color-ca)' }}>
            {summary.cahi.toFixed(2)}
          </span>
          <span className="scorecard-unit">/hr</span>
        </div>
      </div>

      {/* Hypopnea Index */}
      <div className="scorecard-item">
        <div className="scorecard-header">
          <span className="scorecard-label">Hypopnea (HI)</span>
          <span className="scorecard-unit">{hiCount} events</span>
        </div>
        <div className="scorecard-value-row">
          <span className="scorecard-value" style={{ color: 'var(--color-h)' }}>
            {hi}
          </span>
          <span className="scorecard-unit">/hr</span>
        </div>
      </div>

      {/* 95% Percentiles if available */}
      {summary.pressure_95 !== null && (
        <div className="scorecard-item">
          <div className="scorecard-header">
            <span className="scorecard-label">95% Pressure</span>
          </div>
          <div className="scorecard-value-row">
            <span className="scorecard-value" style={{ color: 'var(--color-pressure)' }}>
              {summary.pressure_95.toFixed(1)}
            </span>
            <span className="scorecard-unit">cmH2O</span>
          </div>
        </div>
      )}

      {summary.leak_95 !== null && (
        <div className="scorecard-item">
          <div className="scorecard-header">
            <span className="scorecard-label">95% Leak</span>
          </div>
          <div className="scorecard-value-row">
            <span className="scorecard-value" style={{ color: 'var(--color-leak)' }}>
              {summary.leak_95.toFixed(1)}
            </span>
            <span className="scorecard-unit">L/min</span>
          </div>
        </div>
      )}
    </div>
  );
};
