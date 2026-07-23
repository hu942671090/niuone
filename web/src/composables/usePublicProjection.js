const REFRESH_INTERVAL_MS = 15 * 1000
const REQUEST_TIMEOUT_MS = 15 * 1000
const REFRESH_JITTER_RATIO = 0.12
const CHANNEL_NAME = 'niuone-public-projection-v1'
const POLL_LOCK_NAME = 'niuone-public-projection-poller-v1'

let revision = 0
let etag = ''
let sectionDigests = {}
let refreshTimer = 0
let requestController = null
let refreshRequest = null
let channel = null
let leaderRequest = null
let releaseLeadership = null
let isLeader = false
let projectionStarted = false
let lockCoordinationFailed = false
const subscribers = new Set()

function snapshot() {
  return {
    revision,
    sectionDigests: { ...sectionDigests },
  }
}

function publish(nextSnapshot = snapshot()) {
  for (const subscriber of subscribers) {
    try {
      subscriber.onSnapshot(nextSnapshot)
    } catch (error) {
      console.error('public projection subscriber failed', error)
    }
  }
}

function publishError(error) {
  for (const subscriber of subscribers) {
    if (!subscriber.onError) continue
    try {
      subscriber.onError(error)
    } catch (subscriberError) {
      console.error('public projection error subscriber failed', subscriberError)
    }
  }
}

function pageIsVisible() {
  return document.visibilityState !== 'hidden'
}

function nextRefreshDelay() {
  const spread = REFRESH_INTERVAL_MS * REFRESH_JITTER_RATIO
  return Math.round(REFRESH_INTERVAL_MS - spread + Math.random() * spread * 2)
}

function broadcastSnapshot(nextSnapshot = snapshot()) {
  if (!channel || !isLeader || !nextSnapshot.revision) return
  channel.postMessage({ type: 'snapshot', ...nextSnapshot })
}

function handleChannelMessage(event) {
  const message = event?.data || {}
  if (message.type === 'hello') {
    broadcastSnapshot()
    return
  }
  if (message.type !== 'snapshot') return
  const nextRevision = Number(message.revision || 0)
  const nextDigests = Object.fromEntries(
    Object.entries(message.sectionDigests || {}).filter(([, digest]) => (
      /^[0-9a-f]{64}$/.test(String(digest || ''))
    )),
  )
  if (!Number.isInteger(nextRevision) || nextRevision < revision || !Object.keys(nextDigests).length) return
  revision = nextRevision
  sectionDigests = nextDigests
  publish(snapshot())
}

function ensureChannel() {
  if (channel || typeof window.BroadcastChannel !== 'function') return
  try {
    channel = new window.BroadcastChannel(CHANNEL_NAME)
    channel.addEventListener('message', handleChannelMessage)
  } catch (error) {
    console.warn('public projection tab channel unavailable', error)
    channel = null
  }
}

async function fetchJson(url, controller, options = {}) {
  let timedOut = false
  const timeout = window.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, REQUEST_TIMEOUT_MS)
  try {
    const response = await fetch(url, {
      signal: controller.signal,
      credentials: 'same-origin',
      cache: 'no-store',
      ...options,
    })
    if (response.status === 304) return { notModified: true, response }
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return { payload: await response.json(), response }
  } catch (error) {
    if (timedOut) throw new Error('公开数据版本请求超时')
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function refreshPublicProjection() {
  if (refreshRequest) return refreshRequest
  const controller = new AbortController()
  requestController = controller
  const request = (async () => {
    const headers = etag ? { 'If-None-Match': etag } : {}
    const latestResult = await fetchJson('/api/v2/public/latest', controller, { headers })
    if (latestResult.notModified) {
      const currentSnapshot = snapshot()
      publish(currentSnapshot)
      broadcastSnapshot(currentSnapshot)
      return currentSnapshot
    }
    const latest = latestResult.payload || {}
    const nextRevision = Number(latest.revision || 0)
    if (!Number.isInteger(nextRevision) || nextRevision < 1) throw new Error('公开数据版本无效')
    etag = latestResult.response.headers.get('ETag') || ''
    if (nextRevision === revision && Object.keys(sectionDigests).length) {
      const currentSnapshot = snapshot()
      publish(currentSnapshot)
      broadcastSnapshot(currentSnapshot)
      return currentSnapshot
    }
    const manifestPath = String(latest.manifest || '')
    if (!/^manifests\/[1-9][0-9]*\.json$/.test(manifestPath)) throw new Error('公开数据清单无效')
    const manifestResult = await fetchJson(`/api/v2/public/${manifestPath}`, controller, {
      cache: 'force-cache',
    })
    const nextDigests = {}
    for (const [name, reference] of Object.entries(manifestResult.payload?.sections || {})) {
      const digest = String(reference?.digest || '')
      if (/^[0-9a-f]{64}$/.test(digest)) nextDigests[name] = digest
    }
    if (!Object.keys(nextDigests).length) throw new Error('公开数据清单没有可用区块')
    revision = nextRevision
    sectionDigests = nextDigests
    const nextSnapshot = snapshot()
    publish(nextSnapshot)
    broadcastSnapshot(nextSnapshot)
    return nextSnapshot
  })().catch(error => {
    if (error?.name !== 'AbortError') publishError(error)
    return snapshot()
  }).finally(() => {
    if (requestController === controller) requestController = null
    if (refreshRequest === request) refreshRequest = null
  })
  refreshRequest = request
  return request
}

function clearRefreshTimer() {
  window.clearTimeout(refreshTimer)
  refreshTimer = 0
}

function scheduleLeaderRefresh(delay = nextRefreshDelay()) {
  if (!isLeader || !subscribers.size || !pageIsVisible() || refreshTimer) return
  refreshTimer = window.setTimeout(async () => {
    refreshTimer = 0
    if (!isLeader || !subscribers.size || !pageIsVisible()) return
    await refreshPublicProjection()
    scheduleLeaderRefresh()
  }, delay)
}

function pauseLeaderRefresh() {
  clearRefreshTimer()
  requestController?.abort()
  if (releaseLeadership) {
    const release = releaseLeadership
    releaseLeadership = null
    release()
  } else if (!leaderRequest) {
    isLeader = false
  }
}

function startUncoordinatedRefresh() {
  if (isLeader) return
  isLeader = true
  refreshPublicProjection().finally(() => scheduleLeaderRefresh())
}

function acquireProjectionLeadership() {
  if (!subscribers.size || !pageIsVisible() || isLeader || leaderRequest) return
  const locks = channel && !lockCoordinationFailed ? window.navigator?.locks : null
  if (!locks?.request) {
    startUncoordinatedRefresh()
    return
  }
  const request = locks.request(POLL_LOCK_NAME, async () => {
    if (!subscribers.size || !pageIsVisible()) return
    isLeader = true
    const held = new Promise(resolve => { releaseLeadership = resolve })
    try {
      await refreshPublicProjection()
      scheduleLeaderRefresh()
      await held
    } finally {
      clearRefreshTimer()
      requestController?.abort()
      releaseLeadership = null
      isLeader = false
    }
  }).catch(error => {
    console.warn('public projection tab lock unavailable', error)
    lockCoordinationFailed = true
    startUncoordinatedRefresh()
  }).finally(() => {
    if (leaderRequest === request) leaderRequest = null
    if (subscribers.size && pageIsVisible()) acquireProjectionLeadership()
  })
  leaderRequest = request
}

function handleVisibilityChange() {
  if (!pageIsVisible()) {
    pauseLeaderRefresh()
    return
  }
  channel?.postMessage({ type: 'hello' })
  acquireProjectionLeadership()
}

function startProjectionRefresh() {
  if (!projectionStarted) {
    projectionStarted = true
    ensureChannel()
    document.addEventListener('visibilitychange', handleVisibilityChange)
  }
  channel?.postMessage({ type: 'hello' })
  acquireProjectionLeadership()
}

function stopProjectionRefresh() {
  if (subscribers.size || !projectionStarted) return
  projectionStarted = false
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  pauseLeaderRefresh()
  if (channel) {
    channel.removeEventListener('message', handleChannelMessage)
    channel.close()
    channel = null
  }
}

export function subscribePublicProjection(onSnapshot, onError = null) {
  const subscriber = { onSnapshot, onError }
  subscribers.add(subscriber)
  if (revision && Object.keys(sectionDigests).length) {
    queueMicrotask(() => {
      if (subscribers.has(subscriber)) onSnapshot(snapshot())
    })
  }
  startProjectionRefresh()
  return () => {
    subscribers.delete(subscriber)
    stopProjectionRefresh()
  }
}
