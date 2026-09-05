import type {
  Profile,
  ProfileDetail,
  DayDetail,
  RespiratoryEvent,
  WaveformData,
} from './types';

const API_BASE = '/api';

export async function fetchProfiles(): Promise<Profile[]> {
  const resp = await fetch(`${API_BASE}/profiles`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch profiles: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchProfileDetail(profileId: number): Promise<ProfileDetail> {
  const resp = await fetch(`${API_BASE}/profiles/${profileId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch profile detail: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDays(profileId: number): Promise<string[]> {
  const resp = await fetch(`${API_BASE}/profiles/${profileId}/days`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch days: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDayDetail(
  profileId: number,
  date: string
): Promise<DayDetail> {
  const resp = await fetch(`${API_BASE}/profiles/${profileId}/days/${date}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch day detail for ${date}: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchEvents(
  profileId: number,
  date: string
): Promise<RespiratoryEvent[]> {
  const resp = await fetch(`${API_BASE}/profiles/${profileId}/days/${date}/events`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch events for ${date}: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchWaveform(
  profileId: number,
  sessionId: number,
  channel: string = 'FlowRate',
  points: number = 2000,
  startMs?: number,
  endMs?: number
): Promise<WaveformData | null> {
  const params = new URLSearchParams({
    channel,
    points: points.toString(),
  });
  if (startMs !== undefined) {
    params.set('start_ms', Math.floor(startMs).toString());
  }
  if (endMs !== undefined) {
    params.set('end_ms', Math.floor(endMs).toString());
  }

  const resp = await fetch(
    `${API_BASE}/profiles/${profileId}/sessions/${sessionId}/waveform?${params.toString()}`
  );
  if (resp.status === 404) {
    return null;
  }
  if (!resp.ok) {
    throw new Error(`Failed to fetch waveform for channel ${channel}: ${resp.statusText}`);
  }
  return resp.json();
}
