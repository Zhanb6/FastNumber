const KEY = "ktf_device_token";
const MAX_AGE = 30 * 24 * 60 * 60; // 30 days

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

export function getDeviceToken(): string | null {
  try {
    const fromStorage = window.localStorage.getItem(KEY);
    if (fromStorage) return fromStorage;
  } catch {
    /* storage may be unavailable (private mode) */
  }
  return readCookie(KEY);
}

export function saveDeviceToken(token: string): void {
  try {
    window.localStorage.setItem(KEY, token);
  } catch {
    /* ignore */
  }
  document.cookie = `${KEY}=${encodeURIComponent(token)}; SameSite=Lax; Max-Age=${MAX_AGE}; Path=/`;
}

export function clearDeviceToken(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
  document.cookie = `${KEY}=; SameSite=Lax; Max-Age=0; Path=/`;
}
