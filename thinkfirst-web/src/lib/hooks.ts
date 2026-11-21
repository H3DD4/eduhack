"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

/** Loading is not empty; errors keep the last good data (blueprint: "Loading is not empty"). */
export function useApi<T = any>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const mounted = useRef(true);
  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      const d = await api<T>(path);
      if (mounted.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (mounted.current) setError(e as ApiError);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    mounted.current = true;
    load();
    return () => {
      mounted.current = false;
    };
  }, [load]);
  return { data, error, loading, reload: load, setData };
}

/** Announce once, politely (no timer chatter). */
export function useAnnouncer() {
  const [msg, setMsg] = useState("");
  const announce = useCallback((m: string) => {
    setMsg("");
    setTimeout(() => setMsg(m), 30);
  }, []);
  return { msg, announce };
}
