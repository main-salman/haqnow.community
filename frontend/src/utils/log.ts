// Simple structured logger for frontend
// Usage: logEvent('Comments', 'Add comment clicked', { x, y, page })

type LogPayload = Record<string, unknown> | undefined

const isProd = (import.meta as any)?.env?.MODE === 'production'

export function logEvent(scope: string, message: string, payload?: LogPayload): void {
  try {
    const timestamp = new Date().toISOString()
    // Keep logging in production for now, but make it easy to mute
    // if (isProd) return
    // Consistent, parseable log line
    // eslint-disable-next-line no-console
    console.log(`[%c${scope}%c] ${timestamp} - ${message}`, 'color:#2563eb;font-weight:600', 'color:inherit', payload ?? '')
  } catch {
    // no-op
  }
}

export function logError(scope: string, message: string, payload?: LogPayload): void {
  try {
    const timestamp = new Date().toISOString()
    // eslint-disable-next-line no-console
    console.error(`[%c${scope}%c] ${timestamp} - ${message}`, 'color:#dc2626;font-weight:600', 'color:inherit', payload ?? '')
  } catch {
    // no-op
  }
}

export function logWarn(scope: string, message: string, payload?: LogPayload): void {
  try {
    const timestamp = new Date().toISOString()
    // eslint-disable-next-line no-console
    console.warn(`[%c${scope}%c] ${timestamp} - ${message}`, 'color:#f59e0b;font-weight:600', 'color:inherit', payload ?? '')
  } catch {
    // no-op
  }
}
