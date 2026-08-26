import React, { useCallback, useEffect, useRef, useState } from "react";
import { Video, VideoOff } from "lucide-react";
import { attentionColor } from "../utils/format.js";
import api from "../api/client.js";

const CAPTURE_INTERVAL_MS = 1500;

export default function LiveFeedPanel({ onFrameResult, onCameraStateChange }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);

  const [cameraOn, setCameraOn] = useState(false);
  const [error, setError] = useState(null);
  const [students, setStudents] = useState([]);

  const startCamera = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        "Camera access requires HTTPS (or localhost). This page is being served over an insecure connection."
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        // `ideal` (not exact width/height) lets the browser pick the
        // closest resolution the device actually supports instead of
        // throwing OverconstrainedError on cameras that don't support
        // exactly 1280x720 — this was a real bug: a working camera that
        // only offers e.g. 640x480 or 1920x1080 would previously fail
        // getUserMedia entirely and show "Could not access the camera"
        // even though permission was granted and a camera was present.
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraOn(true);
      onCameraStateChange?.({ active: true, permission: "granted", lastFrameAt: null });
    } catch (err) {
      // Distinguish failure reasons so the message actually tells the
      // person what to do, instead of one generic string for every case.
      let message = "Could not access the camera. Check browser permissions and try again.";
      if (err.name === "NotAllowedError" || err.name === "SecurityError") {
        message = "Camera access was denied. Allow camera permission for this site in your browser settings, then try again.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        message = "No camera was found on this device.";
      } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
        message = "The camera is already in use by another application.";
      } else if (err.name === "OverconstrainedError") {
        message = "This camera doesn't support the requested video settings.";
      }
      setError(message);
      onCameraStateChange?.({
        active: false,
        permission: err.name === "NotAllowedError" || err.name === "SecurityError" ? "denied" : "error",
        lastFrameAt: null,
        error: message,
      });
    }
  }, [onCameraStateChange]);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraOn(false);
    setStudents([]);
    onCameraStateChange?.({ active: false, permission: "granted", lastFrameAt: null });
  }, [onCameraStateChange]);

  // Prevents overlapping /api/process-frame requests: if a previous frame
  // is still being processed when the next interval tick fires, that tick
  // is skipped rather than queued. Without this, a slow backend response
  // (processing takes longer than CAPTURE_INTERVAL_MS) would let requests
  // pile up faster than they resolve.
  const sendingRef = useRef(false);

  const captureAndSend = useCallback(async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;
    if (sendingRef.current) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.7);

    sendingRef.current = true;
    try {
      const result = await api.processFrame(dataUrl);
      setStudents(result.students || []);
      onFrameResult?.(result);
      onCameraStateChange?.({ active: true, permission: "granted", lastFrameAt: Date.now() });
    } catch (err) {
      // Non-fatal: skip this frame, keep the camera running. Surfacing
      // every network hiccup as a UI error would be noisy for a 1.5s poll.
      console.warn("Frame processing failed:", err.message);
    } finally {
      sendingRef.current = false;
    }
  }, [onFrameResult, onCameraStateChange]);

  useEffect(() => {
    if (cameraOn) {
      intervalRef.current = setInterval(captureAndSend, CAPTURE_INTERVAL_MS);
    }
    return () => clearInterval(intervalRef.current);
  }, [cameraOn, captureAndSend]);

  useEffect(() => {
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Draw bounding boxes on the overlay canvas, scaled to the displayed video size.
  useEffect(() => {
    const overlay = overlayRef.current;
    const video = videoRef.current;
    if (!overlay || !video) return;
    const ctx = overlay.getContext("2d");
    overlay.width = video.clientWidth;
    overlay.height = video.clientHeight;
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    if (!video.videoWidth) return;

    const scaleX = overlay.width / video.videoWidth;
    const scaleY = overlay.height / video.videoHeight;

    students.forEach((s) => {
      const { top, right, bottom, left } = s.bbox;
      const x = left * scaleX;
      const y = top * scaleY;
      const w = (right - left) * scaleX;
      const h = (bottom - top) * scaleY;
      const color = attentionColor(s.attention_score);

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x, y, w, h);

      const label = s.is_known ? s.name : "Unknown";
      ctx.font = "600 12px Inter, sans-serif";
      const textWidth = ctx.measureText(label).width;
      ctx.fillStyle = "rgba(10,11,20,0.85)";
      ctx.fillRect(x, y - 20, textWidth + 12, 20);
      ctx.fillStyle = color;
      ctx.fillText(label, x + 6, y - 6);

      ctx.font = "500 11px Inter, sans-serif";
      const scoreLabel = `${Math.round(s.attention_score)}%`;
      ctx.fillStyle = "rgba(10,11,20,0.85)";
      const scoreWidth = ctx.measureText(scoreLabel).width;
      ctx.fillRect(x, y + h, scoreWidth + 12, 18);
      ctx.fillStyle = color;
      ctx.fillText(scoreLabel, x + 6, y + h + 13);
    });
  }, [students]);

  return (
    <div className="glass-panel p-4 col-span-1 lg:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display font-semibold text-slate-100 text-[15px]">
            Live Classroom Feed
          </h2>
          {cameraOn && (
            <span className="flex items-center gap-1.5 text-[11px] font-medium text-accent-red">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
              LIVE
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="glass-card px-3 py-1.5 text-xs text-slate-300">
            Students Detected{" "}
            <span className="font-display font-semibold text-slate-100 ml-1">
              {students.length}
            </span>
          </div>
          <button
            onClick={cameraOn ? stopCamera : startCamera}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-violet-500/90 hover:bg-violet-500 text-white transition-colors"
          >
            {cameraOn ? <VideoOff size={14} /> : <Video size={14} />}
            {cameraOn ? "Stop" : "Start Camera"}
          </button>
        </div>
      </div>

      <div className="relative rounded-xl overflow-hidden bg-black/40 aspect-video">
        <video
          ref={videoRef}
          muted
          playsInline
          className="w-full h-full object-cover"
        />
        <canvas
          ref={overlayRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
        <canvas ref={canvasRef} className="hidden" />

        {!cameraOn && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-500">
            <Video size={28} strokeWidth={1.5} />
            <p className="text-sm">
              {error || "Camera is off — click Start Camera to begin monitoring"}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-slate-400">
        <StatusToggle label="Face Detection" on={cameraOn} />
        <StatusToggle label="Attention Tracking" on={cameraOn} />
        {/* Emotion recognition is not implemented in this project (see
            README "Known Limitations") — never claim it's ON. */}
        <StatusToggle label="Emotion Analysis" on={false} unavailable />
        <StatusToggle label="Attendance" on={cameraOn} />
      </div>
    </div>
  );
}

function StatusToggle({ label, on, unavailable = false }) {
  const text = unavailable ? "N/A" : on ? "ON" : "OFF";
  const cls = unavailable
    ? "bg-white/5 text-slate-600"
    : on
    ? "bg-accent-green/15 text-accent-green"
    : "bg-white/5 text-slate-500";
  return (
    <div className="flex items-center gap-1.5">
      <span className={unavailable ? "text-slate-600" : undefined}>{label}</span>
      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${cls}`}>
        {text}
      </span>
    </div>
  );
}
