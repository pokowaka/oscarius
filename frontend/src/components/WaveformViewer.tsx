import React, { useRef, useEffect, useState, useCallback } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Activity } from 'lucide-react';
import type { WaveformData, RespiratoryEvent, SessionInfo } from '../types';

interface WaveformViewerProps {
  session: SessionInfo;
  flowData: WaveformData | null;
  pressureData: WaveformData | null;
  leakData: WaveformData | null;
  events: RespiratoryEvent[];
  viewWindow: [number, number]; // [startMs, endMs]
  onViewWindowChange: (window: [number, number]) => void;
  isLoading: boolean;
}

export const WaveformViewer: React.FC<WaveformViewerProps> = ({
  session,
  flowData,
  pressureData,
  leakData,
  events,
  viewWindow,
  onViewWindowChange,
  isLoading,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const flowCanvasRef = useRef<HTMLCanvasElement>(null);
  const pressCanvasRef = useRef<HTMLCanvasElement>(null);
  const leakCanvasRef = useRef<HTMLCanvasElement>(null);
  const minimapCanvasRef = useRef<HTMLCanvasElement>(null);

  const [hoverTimeMs, setHoverTimeMs] = useState<number | null>(null);
  const [hoverValues, setHoverValues] = useState<{
    flow?: number;
    pressure?: number;
    leak?: number;
  }>({});
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const dragStartXRef = useRef<number>(0);
  const dragStartWindowRef = useRef<[number, number]>([0, 0]);

  const [viewStartMs, viewEndMs] = viewWindow;
  const sessionStartMs = session.start_time;
  const sessionEndMs = session.end_time;
  const sessionDurationMs = Math.max(1, sessionEndMs - sessionStartMs);

  // Time to formatted string
  const formatTime = (timeMs: number): string => {
    const d = new Date(timeMs);
    return d.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  // Binary search for nearest value in downsampled waveform
  const getNearestValue = (wf: WaveformData | null, targetTimeMs: number): number | undefined => {
    if (!wf || !wf.timestamps_ms || wf.timestamps_ms.length === 0) return undefined;
    const ts = wf.timestamps_ms;
    let low = 0;
    let high = ts.length - 1;
    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (ts[mid] < targetTimeMs) {
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    const idx = Math.max(0, Math.min(low, ts.length - 1));
    return wf.values[idx];
  };

  // Render a waveform track on a specific canvas
  const drawTrack = useCallback(
    (
      canvas: HTMLCanvasElement | null,
      data: WaveformData | null,
      color: string,
      yMin: number,
      yMax: number,
      unit: string,
      baselineZero: boolean = false,
      drawEvents: boolean = false,
      redlineThreshold?: number
    ) => {
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);

      const width = rect.width;
      const height = rect.height;
      const paddingBottom = 4;
      const paddingTop = 14;
      const plotHeight = height - paddingTop - paddingBottom;

      ctx.clearRect(0, 0, width, height);

      // Background grid lines (horizontal)
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      const gridSteps = 4;
      for (let i = 0; i <= gridSteps; i++) {
        const yVal = yMin + ((yMax - yMin) * i) / gridSteps;
        const yPix = paddingTop + plotHeight - ((yVal - yMin) / (yMax - yMin)) * plotHeight;
        ctx.beginPath();
        ctx.moveTo(0, yPix);
        ctx.lineTo(width, yPix);
        ctx.stroke();

        // Label on left
        ctx.fillStyle = '#64748b';
        ctx.font = '9px monospace';
        ctx.fillText(yVal.toFixed(0), 4, yPix - 2);
      }

      // Zero baseline if requested
      if (baselineZero && yMin < 0 && yMax > 0) {
        const zeroY = paddingTop + plotHeight - ((0 - yMin) / (yMax - yMin)) * plotHeight;
        ctx.strokeStyle = '#475569';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(0, zeroY);
        ctx.lineTo(width, zeroY);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // Redline threshold if requested (e.g. 24 L/min leak)
      if (redlineThreshold !== undefined && yMin <= redlineThreshold && redlineThreshold <= yMax) {
        const redlineY =
          paddingTop + plotHeight - ((redlineThreshold - yMin) / (yMax - yMin)) * plotHeight;
        ctx.strokeStyle = '#ef4444';
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(0, redlineY);
        ctx.lineTo(width, redlineY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#ef4444';
        ctx.font = '10px sans-serif';
        ctx.fillText(`24 ${unit} (Redline)`, width - 110, redlineY - 4);
      }

      // Draw Respiratory Events if enabled (e.g. on FlowRate)
      if (drawEvents && events && events.length > 0) {
        events.forEach((ev) => {
          const evStart = ev.start_time_ms;
          const evEnd = evStart + ev.duration * 1000;
          if (evEnd < viewStartMs || evStart > viewEndMs) return;

          const xStart = ((evStart - viewStartMs) / (viewEndMs - viewStartMs)) * width;
          const xEnd = ((evEnd - viewStartMs) / (viewEndMs - viewStartMs)) * width;
          const rectW = Math.max(3, xEnd - xStart);

          const code = ev.channel_code.toLowerCase();
          let bandColor = 'rgba(239, 68, 68, 0.25)'; // OA
          let tagColor = '#ef4444';
          let tagText = 'OA';
          if (code.includes('central') || code.includes('clearairway') || code === 'ca') {
            bandColor = 'rgba(6, 182, 212, 0.25)';
            tagColor = '#06b6d4';
            tagText = 'CA';
          } else if (code.includes('hypopnea') || code === 'h') {
            bandColor = 'rgba(245, 158, 11, 0.25)';
            tagColor = '#f59e0b';
            tagText = 'H';
          }

          // Shaded box
          ctx.fillStyle = bandColor;
          ctx.fillRect(xStart, paddingTop, rectW, plotHeight);

          // Top label tag
          ctx.fillStyle = tagColor;
          ctx.fillRect(xStart, 0, Math.max(rectW, 30), 12);
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 8px sans-serif';
          ctx.fillText(`${tagText} ${ev.duration}s`, xStart + 2, 9);
        });
      }

      // Plot Signal Line
      if (data && data.timestamps_ms && data.timestamps_ms.length > 0) {
        const ts = data.timestamps_ms;
        const vals = data.values;
        const count = ts.length;

        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();

        let started = false;
        for (let i = 0; i < count; i++) {
          const t = ts[i];
          const x = ((t - viewStartMs) / (viewEndMs - viewStartMs)) * width;
          const val = Math.max(yMin, Math.min(yMax, vals[i]));
          const y = paddingTop + plotHeight - ((val - yMin) / (yMax - yMin)) * plotHeight;

          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }

      // Synchronized Hover Crosshair Line
      if (hoverTimeMs !== null && hoverTimeMs >= viewStartMs && hoverTimeMs <= viewEndMs) {
        const hoverX = ((hoverTimeMs - viewStartMs) / (viewEndMs - viewStartMs)) * width;
        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = 1;
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(hoverX, 0);
        ctx.lineTo(hoverX, height);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    },
    [viewStartMs, viewEndMs, events, hoverTimeMs]
  );

  // Render Minimap Overview
  const drawMinimap = useCallback(() => {
    const canvas = minimapCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    ctx.clearRect(0, 0, width, height);

    // Mini waveform representation
    if (flowData && flowData.timestamps_ms) {
      const ts = flowData.timestamps_ms;
      const vals = flowData.values;
      const count = ts.length;
      ctx.strokeStyle = '#0284c7';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < count; i += 4) {
        const t = ts[i];
        const x = ((t - sessionStartMs) / sessionDurationMs) * width;
        const val = Math.max(-50, Math.min(50, vals[i]));
        const y = height / 2 - (val / 50) * (height / 2);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }

    // Mini event markers
    if (events) {
      events.forEach((ev) => {
        const x = ((ev.start_time_ms - sessionStartMs) / sessionDurationMs) * width;
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(x, 0, 2, height);
      });
    }

    // Viewport selection rectangle
    const selX1 = Math.max(0, ((viewStartMs - sessionStartMs) / sessionDurationMs) * width);
    const selX2 = Math.min(width, ((viewEndMs - sessionStartMs) / sessionDurationMs) * width);
    const selW = Math.max(4, selX2 - selX1);

    ctx.fillStyle = 'rgba(56, 189, 248, 0.2)';
    ctx.fillRect(selX1, 0, selW, height);
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(selX1, 0, selW, height);
  }, [flowData, events, sessionStartMs, sessionDurationMs, viewStartMs, viewEndMs]);

  // Redraw all canvases when data, viewWindow, or hover changes
  useEffect(() => {
    drawTrack(flowCanvasRef.current, flowData, '#38bdf8', -60, 60, 'L/min', true, true);
    drawTrack(pressCanvasRef.current, pressureData, '#34d399', 4, 20, 'cmH2O', false, false);
    drawTrack(leakCanvasRef.current, leakData, '#fbbf24', 0, 40, 'L/min', false, false, 24);
    drawMinimap();
  }, [drawTrack, drawMinimap, flowData, pressureData, leakData]);

  // Handle Mouse Move over tracks (Synchronized Crosshair)
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const fraction = x / rect.width;
    const timeAtCursor = Math.round(viewStartMs + fraction * (viewEndMs - viewStartMs));
    setHoverTimeMs(timeAtCursor);

    setHoverValues({
      flow: getNearestValue(flowData, timeAtCursor),
      pressure: getNearestValue(pressureData, timeAtCursor),
      leak: getNearestValue(leakData, timeAtCursor),
    });

    // Panning drag
    if (isDragging) {
      const deltaX = e.clientX - dragStartXRef.current;
      const deltaTime = -(deltaX / rect.width) * (dragStartWindowRef.current[1] - dragStartWindowRef.current[0]);
      let newStart = dragStartWindowRef.current[0] + deltaTime;
      let newEnd = dragStartWindowRef.current[1] + deltaTime;

      if (newStart < sessionStartMs) {
        newEnd += sessionStartMs - newStart;
        newStart = sessionStartMs;
      }
      if (newEnd > sessionEndMs) {
        newStart -= newEnd - sessionEndMs;
        newEnd = sessionEndMs;
      }
      onViewWindowChange([Math.round(newStart), Math.round(newEnd)]);
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return; // only left click
    setIsDragging(true);
    dragStartXRef.current = e.clientX;
    dragStartWindowRef.current = [...viewWindow];
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleMouseLeave = () => {
    setIsDragging(false);
    setHoverTimeMs(null);
  };

  // Wheel zoom centered on cursor
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const cursorFraction = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const currentSpan = viewEndMs - viewStartMs;

    const zoomFactor = e.deltaY > 0 ? 1.25 : 0.8; // zoom out or zoom in
    const minSpan = 15 * 1000; // 15 seconds minimum window
    const maxSpan = sessionDurationMs;
    const newSpan = Math.max(minSpan, Math.min(maxSpan, currentSpan * zoomFactor));

    const cursorTime = viewStartMs + cursorFraction * currentSpan;
    let newStart = cursorTime - cursorFraction * newSpan;
    let newEnd = newStart + newSpan;

    if (newStart < sessionStartMs) {
      newStart = sessionStartMs;
      newEnd = Math.min(sessionEndMs, newStart + newSpan);
    }
    if (newEnd > sessionEndMs) {
      newEnd = sessionEndMs;
      newStart = Math.max(sessionStartMs, newEnd - newSpan);
    }

    onViewWindowChange([Math.round(newStart), Math.round(newEnd)]);
  };

  // Zoom buttons
  const zoom = (factor: number) => {
    const currentSpan = viewEndMs - viewStartMs;
    const center = (viewStartMs + viewEndMs) / 2;
    const newSpan = Math.max(15 * 1000, Math.min(sessionDurationMs, currentSpan * factor));
    const newStart = Math.max(sessionStartMs, center - newSpan / 2);
    const newEnd = Math.min(sessionEndMs, center + newSpan / 2);
    onViewWindowChange([Math.round(newStart), Math.round(newEnd)]);
  };

  const resetZoom = () => {
    onViewWindowChange([sessionStartMs, sessionEndMs]);
  };

  // Minimap click navigation
  const handleMinimapClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const fraction = (e.clientX - rect.left) / rect.width;
    const clickTime = sessionStartMs + fraction * sessionDurationMs;
    const span = viewEndMs - viewStartMs;
    let newStart = clickTime - span / 2;
    let newEnd = clickTime + span / 2;

    if (newStart < sessionStartMs) {
      newStart = sessionStartMs;
      newEnd = Math.min(sessionEndMs, newStart + span);
    }
    if (newEnd > sessionEndMs) {
      newEnd = sessionEndMs;
      newStart = Math.max(sessionStartMs, newEnd - span);
    }
    onViewWindowChange([Math.round(newStart), Math.round(newEnd)]);
  };

  return (
    <div className="waveform-panel" ref={containerRef}>
      {/* Waveform Controls Header */}
      <div className="waveform-toolbar">
        <div className="session-selector">
          <Activity size={16} color="var(--color-flow)" />
          <span style={{ fontWeight: 600 }}>
            Session #{session.id} ({session.duration_hours.toFixed(1)}h)
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            {formatTime(session.start_time)} &rarr; {formatTime(session.end_time)}
          </span>
          {isLoading && (
            <span style={{ color: 'var(--color-flow)', fontSize: '0.75rem', fontStyle: 'italic' }}>
              Loading high-res...
            </span>
          )}
        </div>

        <div className="toolbar-actions">
          <button className="action-btn" onClick={() => zoom(0.6)} title="Zoom In">
            <ZoomIn size={14} /> Zoom In
          </button>
          <button className="action-btn" onClick={() => zoom(1.5)} title="Zoom Out">
            <ZoomOut size={14} /> Zoom Out
          </button>
          <button className="action-btn" onClick={resetZoom} title="Reset View to Full Session">
            <RotateCcw size={14} /> Reset
          </button>
        </div>
      </div>

      {/* Synchronized Multi-Track Canvases */}
      <div
        className="tracks-container"
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        style={{ cursor: isDragging ? 'grabbing' : 'crosshair' }}
      >
        {/* Track 1: Flow Rate */}
        <div className="track-wrapper" style={{ height: 160 }}>
          <div className="track-header">
            <span className="track-title track-flow">Flow Rate</span>
            <span className="track-val-badge" style={{ color: 'var(--color-flow)' }}>
              {hoverValues.flow !== undefined ? `${hoverValues.flow.toFixed(1)} L/m` : '0.0 L/m'}
            </span>
          </div>
          <canvas ref={flowCanvasRef} className="waveform-canvas" style={{ height: 160 }} />
        </div>

        {/* Track 2: Mask Pressure */}
        <div className="track-wrapper" style={{ height: 95 }}>
          <div className="track-header">
            <span className="track-title track-press">Pressure</span>
            <span className="track-val-badge" style={{ color: 'var(--color-pressure)' }}>
              {hoverValues.pressure !== undefined
                ? `${hoverValues.pressure.toFixed(1)} cmH2O`
                : '-- cmH2O'}
            </span>
          </div>
          <canvas ref={pressCanvasRef} className="waveform-canvas" style={{ height: 95 }} />
        </div>

        {/* Track 3: Leak Rate */}
        <div className="track-wrapper" style={{ height: 95 }}>
          <div className="track-header">
            <span className="track-title track-leak">Leak</span>
            <span className="track-val-badge" style={{ color: 'var(--color-leak)' }}>
              {hoverValues.leak !== undefined ? `${hoverValues.leak.toFixed(1)} L/m` : '-- L/m'}
            </span>
          </div>
          <canvas ref={leakCanvasRef} className="waveform-canvas" style={{ height: 95 }} />
        </div>
      </div>

      {/* Minimap Overview & Time Slider */}
      <div style={{ marginTop: '0.25rem' }}>
        <div
          className="minimap-wrapper"
          onClick={handleMinimapClick}
          title="Click to jump timeline viewport"
        >
          <canvas ref={minimapCanvasRef} className="minimap-canvas" />
        </div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            marginTop: '0.35rem',
          }}
        >
          <span>View: {formatTime(viewStartMs)}</span>
          {hoverTimeMs !== null && (
            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
              Cursor: {formatTime(hoverTimeMs)}
            </span>
          )}
          <span>{formatTime(viewEndMs)}</span>
        </div>
      </div>
    </div>
  );
};
