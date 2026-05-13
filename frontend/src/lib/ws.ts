const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"

type EventHandler = (event: { event_type: string; payload: Record<string, unknown> }) => void

export class RunCardSocket {
  private ws: WebSocket | null = null
  private handlers: EventHandler[] = []
  private runcardId: string

  constructor(runcardId: string) {
    this.runcardId = runcardId
  }

  connect() {
    this.ws = new WebSocket(`${WS_URL}/ws/runcard/${this.runcardId}`)
    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        this.handlers.forEach((h) => h(data))
      } catch {}
    }
    this.ws.onerror = () => setTimeout(() => this.connect(), 3000)
    return this
  }

  on(handler: EventHandler) {
    this.handlers.push(handler)
    return this
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }
}
