/**
 * pollingController — lightweight adaptive polling for the dashboard.
 *
 * Polls /status and /ingestion/progress together.
 * - ACTIVE cadence (3 s): when a run is in progress or progress.phase !== "idle"
 * - IDLE cadence (30 s):  when everything is quiet
 *
 * Guards against overlapping in-flight requests: if the previous pair of
 * fetches hasn't resolved yet the tick is skipped entirely.
 *
 * Teardown: call controller.stop() when the page is torn down / navigated away.
 */

import type { IAiApiClient } from "../types/api";
import type { IAiStatusResponse, IIngestionProgress } from "../types/status";

const ACTIVE_INTERVAL_MS = 3_000;
const IDLE_INTERVAL_MS   = 30_000;

export interface PollSnapshot {
  status: IAiStatusResponse;
  progress: IIngestionProgress;
}

export type PollCallback = (snap: PollSnapshot) => void;
export type PollErrorCallback = (err: unknown) => void;

export interface PollingController {
  /** Cancel all pending ticks. Safe to call multiple times. */
  stop(): void;
}

/** Returns true when the polling cadence should be ACTIVE (fast). */
function isActive(snap: PollSnapshot): boolean {
  return (
    snap.progress.phase !== "idle" ||
    snap.status.lastIngestionRun?.status === "running"
  );
}

export function createPollingController(
  client: IAiApiClient,
  onTick: PollCallback,
  onError?: PollErrorCallback,
): PollingController {
  let timerId: ReturnType<typeof setTimeout> | null = null;
  let stopped = false;
  let inFlight = false;

  async function tick(): Promise<void> {
    if (stopped) return;
    if (inFlight) {
      // Previous pair of requests still pending — skip this tick, reschedule
      schedule(ACTIVE_INTERVAL_MS);
      return;
    }

    inFlight = true;
    try {
      const [statusResult, progressResult] = await Promise.all([
        client.getStatus(),
        client.getIngestionProgress(),
      ]);

      if (stopped) return;

      if (!statusResult.ok || !progressResult.ok) {
        // On error, keep polling at idle cadence; surface via optional callback
        if (!statusResult.ok) {
          onError?.(statusResult.error);
        } else if (!progressResult.ok) {
          onError?.(progressResult.error);
        }
        schedule(IDLE_INTERVAL_MS);
        return;
      }

      const snap: PollSnapshot = {
        status:   statusResult.data,
        progress: progressResult.data,
      };

      onTick(snap);
      schedule(isActive(snap) ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS);
    } catch (err) {
      if (!stopped) {
        onError?.(err);
        schedule(IDLE_INTERVAL_MS);
      }
    } finally {
      inFlight = false;
    }
  }

  function schedule(delayMs: number): void {
    if (stopped) return;
    if (timerId !== null) clearTimeout(timerId);
    timerId = setTimeout(() => { void tick(); }, delayMs);
  }

  // Kick off immediately
  schedule(0);

  return {
    stop(): void {
      stopped = true;
      if (timerId !== null) {
        clearTimeout(timerId);
        timerId = null;
      }
    },
  };
}
