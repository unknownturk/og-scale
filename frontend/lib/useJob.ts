"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Job } from "./types";

const INTERVAL_MS = 1500;
const GIVE_UP_MS = 5 * 60 * 1000;

type State<R> = { running: boolean; error: string; result: R | null };

/** Verfolgt einen Hintergrund-Auftrag. Erfolg und Fehler sind getrennt, und
 *  nach fünf Minuten ohne Ergebnis hört das Warten mit einer Meldung auf. */
export function useJob<R>(onSuccess?: (result: R) => void) {
  const [state, setState] = useState<State<R>>({ running: false, error: "", result: null });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const done = useRef(onSuccess);
  done.current = onSuccess;

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const track = useCallback(async (start: () => Promise<Job>) => {
    setState({ running: true, error: "", result: null });
    const began = Date.now();
    const fail = (error: string) => setState({ running: false, error, result: null });
    let job: Job;
    try {
      job = await start();
    } catch (e) {
      return fail((e as Error).message);
    }
    const check = async (current: Job) => {
      if (current.status === "succeeded") {
        setState({ running: false, error: "", result: current.result as R });
        done.current?.(current.result as R);
        return;
      }
      if (current.status === "failed") return fail(current.error || "Der Auftrag ist fehlgeschlagen.");
      if (Date.now() - began > GIVE_UP_MS) {
        return fail("Das dauert ungewöhnlich lange. Lade die Seite neu, um den Stand zu sehen.");
      }
      timer.current = setTimeout(async () => {
        try {
          check(await api.getJob(current.id));
        } catch (e) {
          fail((e as Error).message);
        }
      }, INTERVAL_MS);
    };
    check(job);
  }, []);

  const reset = useCallback(() => setState({ running: false, error: "", result: null }), []);
  return { ...state, track, reset };
}
