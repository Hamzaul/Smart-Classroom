import { useEffect, useRef, useState } from "react";

/**
 * Polls an async fetcher function on an interval and exposes
 * { data, error, loading, refetch }. Pauses polling when the tab is
 * hidden to avoid wasting requests/battery on backgrounded devices.
 */
export function usePolling(fetcher, intervalMs = 5000, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);
  const fetcherRef = useRef(fetcher);
  const inFlightRef = useRef(false);
  const mountedRef = useRef(true);
  fetcherRef.current = fetcher;

  const run = async () => {
    // Guard against overlapping requests: if a previous poll is still
    // in flight (e.g. a slow network response taking longer than the
    // poll interval), skip this tick rather than stacking up concurrent
    // requests that arrive out of order and cause flickering data.
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    try {
      const result = await fetcherRef.current();
      if (mountedRef.current) {
        setData(result);
        setError(null);
      }
    } catch (err) {
      if (mountedRef.current) setError(err);
    } finally {
      inFlightRef.current = false;
      if (mountedRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    mountedRef.current = true;
    run();
    const tick = () => {
      if (document.visibilityState === "visible") {
        run();
      }
    };
    timerRef.current = setInterval(tick, intervalMs);
    return () => {
      mountedRef.current = false;
      clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, refetch: run };
}
