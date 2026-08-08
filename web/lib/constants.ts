/**
 * Values shared between the Edge middleware and the Node route handlers.
 *
 * Kept free of any Node import: middleware runs on the Edge runtime, and
 * pulling `node:crypto` in through a shared module fails the build.
 */
export const SESSION_COOKIE = "ta_session";
export const SESSION_TTL_SECONDS = 60 * 60 * 12;
