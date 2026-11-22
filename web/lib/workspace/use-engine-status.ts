import { useEffect, useState } from "react";
import { getFormats, getHealth, getSamples } from "../engine-client";
import type { Formats, Health, Sample } from "../types";

export type EngineState = { status: "checking" | "up" | "down"; health?: Health; message?: string };

const HEALTHY_RECHECK_MS = 60_000;
const DOWN_RECHECK_MS = 8_000;

export function useEngineStatus(): { engine: EngineState; formats: Formats | null; samples: Sample[] } {
  const [engine, setEngine] = useState<EngineState>({ status: "checking" });
  const [formats, setFormats] = useState<Formats | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    const check = async () => {
      try {
        const health = await getHealth();
        if (!alive) return;
        setEngine({ status: "up", health });
        if (!formats) getFormats().then(setFormats).catch(() => {});
        if (!samples.length) getSamples().then(setSamples).catch(() => {});
        timer = setTimeout(check, HEALTHY_RECHECK_MS);
      } catch (e) {
        if (!alive) return;
        setEngine({ status: "down", message: e instanceof Error ? e.message : String(e) });
        timer = setTimeout(check, DOWN_RECHECK_MS);
      }
    };
    check();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { engine, formats, samples };
}
