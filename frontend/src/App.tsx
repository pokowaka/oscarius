import React, { useEffect, useState, useCallback } from 'react';
import { Header } from './components/Header';
import { DailyScorecard } from './components/DailyScorecard';
import { WaveformViewer } from './components/WaveformViewer';
import { EventsTable } from './components/EventsTable';
import type {
  Profile,
  Machine,
  DayDetail,
  RespiratoryEvent,
  SessionInfo,
  WaveformData,
} from './types';
import {
  fetchProfiles,
  fetchProfileDetail,
  fetchDays,
  fetchDayDetail,
  fetchEvents,
  fetchWaveform,
} from './api';

export const App: React.FC = () => {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null);
  const [activeMachine, setActiveMachine] = useState<Machine | null>(null);

  const [availableDays, setAvailableDays] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');

  const [dayDetail, setDayDetail] = useState<DayDetail | null>(null);
  const [events, setEvents] = useState<RespiratoryEvent[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  const [selectedSession, setSelectedSession] = useState<SessionInfo | null>(null);
  const [viewWindow, setViewWindow] = useState<[number, number]>([0, 0]);

  const [flowData, setFlowData] = useState<WaveformData | null>(null);
  const [pressureData, setPressureData] = useState<WaveformData | null>(null);
  const [leakData, setLeakData] = useState<WaveformData | null>(null);

  const [isLoadingWaveforms, setIsLoadingWaveforms] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 1. Initial Load: Fetch profiles
  useEffect(() => {
    fetchProfiles()
      .then((data) => {
        setProfiles(data);
        if (data.length > 0) {
          setSelectedProfileId(data[0].id);
        }
      })
      .catch((err) => {
        console.error('Failed to load profiles:', err);
        setErrorMsg('Unable to connect to Oscarius backend. Please verify the server is running.');
      });
  }, []);

  // 2. Profile Changed: Fetch profile detail & available days
  useEffect(() => {
    if (!selectedProfileId) return;

    fetchProfileDetail(selectedProfileId)
      .then((detail) => {
        if (detail.machines && detail.machines.length > 0) {
          setActiveMachine(detail.machines[0]);
        } else {
          setActiveMachine(null);
        }
      })
      .catch(console.error);

    fetchDays(selectedProfileId)
      .then((days) => {
        setAvailableDays(days);
        if (days.length > 0) {
          // Default to most recent day
          setSelectedDate(days[days.length - 1]);
        } else {
          setSelectedDate('');
          setDayDetail(null);
          setEvents([]);
        }
      })
      .catch(console.error);
  }, [selectedProfileId]);

  // 3. Date Changed: Fetch day details and events
  useEffect(() => {
    if (!selectedProfileId || !selectedDate) return;

    fetchDayDetail(selectedProfileId, selectedDate)
      .then((detail) => {
        setDayDetail(detail);
        if (detail.sessions && detail.sessions.length > 0) {
          const firstSess = detail.sessions[0];
          setSelectedSession(firstSess);
          setViewWindow([firstSess.start_time, firstSess.end_time]);
        } else {
          setSelectedSession(null);
          setViewWindow([0, 0]);
        }
      })
      .catch(console.error);

    fetchEvents(selectedProfileId, selectedDate)
      .then((evs) => setEvents(evs))
      .catch(console.error);
  }, [selectedProfileId, selectedDate]);

  // 4. Load Waveforms for Selected Session and View Window
  const loadWaveforms = useCallback(async () => {
    if (!selectedProfileId || !selectedSession) {
      setFlowData(null);
      setPressureData(null);
      setLeakData(null);
      return;
    }

    setIsLoadingWaveforms(true);
    try {
      const [fData, pData, lData] = await Promise.all([
        fetchWaveform(
          selectedProfileId,
          selectedSession.id,
          'FlowRate',
          2000,
          viewWindow[0],
          viewWindow[1]
        ),
        fetchWaveform(
          selectedProfileId,
          selectedSession.id,
          'Pressure',
          1000,
          viewWindow[0],
          viewWindow[1]
        ),
        fetchWaveform(
          selectedProfileId,
          selectedSession.id,
          'Leak',
          1000,
          viewWindow[0],
          viewWindow[1]
        ),
      ]);

      setFlowData(fData);
      setPressureData(pData);
      setLeakData(lData);
    } catch (err) {
      console.error('Failed to load waveforms:', err);
    } finally {
      setIsLoadingWaveforms(false);
    }
  }, [selectedProfileId, selectedSession, viewWindow]);

  // Debounced load when viewWindow or session changes
  useEffect(() => {
    const timer = setTimeout(() => {
      loadWaveforms();
    }, 120);
    return () => clearTimeout(timer);
  }, [loadWaveforms]);

  // Handle clicking an event in the events log
  const handleSelectEvent = (ev: RespiratoryEvent) => {
    setSelectedEventId(ev.id);

    // If event is in a different session, switch session
    if (dayDetail && dayDetail.sessions) {
      const matchingSession = dayDetail.sessions.find((s) => s.id === ev.session_id);
      if (matchingSession && matchingSession.id !== selectedSession?.id) {
        setSelectedSession(matchingSession);
      }
    }

    // Zoom into event with 30s context window before and after
    const contextMs = 30 * 1000;
    const start = Math.max(
      selectedSession ? selectedSession.start_time : 0,
      ev.start_time_ms - contextMs
    );
    const end = Math.min(
      selectedSession ? selectedSession.end_time : ev.start_time_ms + contextMs * 2,
      ev.start_time_ms + (ev.duration * 1000) + contextMs
    );
    setViewWindow([start, end]);
  };

  return (
    <div className="app-container">
      <Header
        profiles={profiles}
        selectedProfileId={selectedProfileId}
        onSelectProfile={setSelectedProfileId}
        availableDays={availableDays}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
        activeMachine={activeMachine}
      />

      <main className="main-content">
        {errorMsg && (
          <div
            style={{
              padding: '0.75rem 1rem',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid var(--color-danger)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-danger)',
              fontSize: '0.875rem',
            }}
          >
            {errorMsg}
          </div>
        )}

        {/* Clinical Scorecard */}
        <DailyScorecard summary={dayDetail?.summary || null} />

        {/* Main Workspace: Waveform Canvas + Events Sidebar */}
        <div className="workspace-grid">
          {selectedSession ? (
            <WaveformViewer
              session={selectedSession}
              flowData={flowData}
              pressureData={pressureData}
              leakData={leakData}
              events={events.filter((e) => e.session_id === selectedSession.id)}
              viewWindow={viewWindow}
              onViewWindowChange={setViewWindow}
              isLoading={isLoadingWaveforms}
            />
          ) : (
            <div
              className="waveform-panel empty-state"
              style={{ minHeight: 450, justifyContent: 'center' }}
            >
              <span className="empty-state-title">No CPAP therapy sessions found</span>
              <span style={{ fontSize: '0.875rem' }}>
                Select a different date from the header or import ResMed SD card data using the CLI.
              </span>
            </div>
          )}

          {/* Events Log Sidebar */}
          <EventsTable
            events={events}
            selectedEventId={selectedEventId}
            onSelectEvent={handleSelectEvent}
          />
        </div>
      </main>
    </div>
  );
};

export default App;
