/**
 * Best-effort brute-force protection for the login endpoint.
 *
 * Honest about its limits: this is per-instance memory, and Vercel runs many
 * short-lived instances, so a distributed attacker can get more attempts than
 * the nominal budget by spreading requests across cold starts. It still turns
 * a trivially scriptable password guess against one warm instance into
 * something slow, which is worth having in front of a dashboard that can
 * trade. A strong DASHBOARD_PASSWORD remains the actual defence; for a hard
 * guarantee, put the deployment behind Vercel Authentication or an IP allow
 * list.
 */
const WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 8;

type Bucket = { count: number; resetAt: number };

const buckets = new Map<string, Bucket>();

function prune(now: number) {
  for (const [key, bucket] of buckets) {
    if (bucket.resetAt <= now) buckets.delete(key);
  }
}

/** Identify the caller. Falls back to a shared bucket when no IP is present. */
export function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded?.split(",")[0]?.trim() || "unknown";
}

/** Record an attempt. Returns how long to wait, or 0 when allowed. */
export function checkRateLimit(key: string): number {
  const now = Date.now();
  prune(now);

  const bucket = buckets.get(key);
  if (!bucket || bucket.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + WINDOW_MS });
    return 0;
  }

  bucket.count += 1;
  if (bucket.count > MAX_ATTEMPTS) {
    return Math.ceil((bucket.resetAt - now) / 1000);
  }
  return 0;
}

/** Clear the counter after a successful sign-in. */
export function resetRateLimit(key: string): void {
  buckets.delete(key);
}
