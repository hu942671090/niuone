const DEFAULT_JITTER_RATIO = 0.12

function pageIsVisible() {
  return typeof document === 'undefined' || document.visibilityState !== 'hidden'
}

function jitteredDelay(intervalMs, jitterRatio) {
  const interval = Math.max(1, Number(intervalMs) || 1)
  const ratio = Math.min(0.5, Math.max(0, Number(jitterRatio) || 0))
  const spread = interval * ratio
  return Math.max(1, Math.round(interval - spread + Math.random() * spread * 2))
}

export function startVisiblePolling(callback, intervalMs, options = {}) {
  const jitterRatio = options.jitterRatio ?? DEFAULT_JITTER_RATIO
  let stopped = false
  let running = false
  let timer = 0

  function clearTimer() {
    window.clearTimeout(timer)
    timer = 0
  }

  function schedule(delay = jitteredDelay(intervalMs, jitterRatio)) {
    if (stopped || running || timer || !pageIsVisible()) return
    timer = window.setTimeout(run, delay)
  }

  async function run() {
    timer = 0
    if (stopped || running || !pageIsVisible()) return
    running = true
    try {
      await callback()
    } catch (error) {
      console.error('visible polling callback failed', error)
    } finally {
      running = false
      schedule()
    }
  }

  function handleVisibilityChange() {
    if (!pageIsVisible()) {
      clearTimer()
      return
    }
    schedule(0)
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)
  if (options.runImmediately) run()
  else schedule()

  return () => {
    if (stopped) return
    stopped = true
    clearTimer()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }
}
