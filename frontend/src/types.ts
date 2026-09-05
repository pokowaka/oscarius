export interface Profile {
  id: number;
  username: string;
  status: string;
  data_folder: string | null;
}

export interface Machine {
  id: number;
  profile_id: number;
  machine_id: number;
  loader_name: string;
  machine_type: number;
  brand: string;
  model: string;
  serial_number: string;
}

export interface ProfileDetail {
  profile: Profile;
  machines: Machine[];
}

export interface DailySummary {
  date: string;
  total_hours: number;
  ahi: number;
  oahi: number;
  cahi: number;
  obstructive_hypopnea_count: number;
  central_hypopnea_count: number;
  all_apnea_count: number;
  leak_95: number | null;
  pressure_95: number | null;
  compliance_flag: number;
}

export interface SessionInfo {
  id: number;
  machine_id: number;
  start_time: number; // ms
  end_time: number;   // ms
  duration_hours: number;
  brand?: string;
  model?: string;
}

export interface DayDetail {
  date: string;
  summary: DailySummary | null;
  sessions: SessionInfo[];
}

export interface RespiratoryEvent {
  id: number;
  session_id: number;
  channel_code: string;
  start_time_ms: number;
  duration: number; // in seconds
  label: string | null;
  fullname: string | null;
}

export interface WaveformData {
  session_id: number;
  channel_code: string;
  sample_rate: number;
  first_time_ms: number;
  last_time_ms: number;
  total_points: number;
  downsampled_points: number;
  timestamps_ms: number[];
  values: number[];
}
