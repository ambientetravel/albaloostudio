import type { ClientMessage, ServerMessage } from './protocol';

export type ConnState = 'idle' | 'connecting' | 'online' | 'offline';

type Listener = (msg: ServerMessage) => void;
type StateListener = (state: ConnState) => void;

/**
 * Thin WebSocket wrapper with backoff reconnect.
 *
 * The game must stay fully playable when this never connects, so every failure
 * path here just ends in `offline` — the menu greys out online play and vs-AI
 * carries on untouched.
 */
class NetClient {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private stateListeners = new Set<StateListener>();
  private state: ConnState = 'idle';
  private retry = 0;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private identity: { name: string; avatar: number; arena: number; deck: string[]; commander: string } | null = null;
  private wantConnection = false;

  get connectionState(): ConnState {
    return this.state;
  }

  onMessage(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  onState(fn: StateListener): () => void {
    this.stateListeners.add(fn);
    return () => this.stateListeners.delete(fn);
  }

  private setState(s: ConnState): void {
    if (this.state === s) return;
    this.state = s;
    for (const fn of this.stateListeners) fn(s);
  }

  private url(): string {
    const override = import.meta.env.VITE_WS_URL;
    if (override) return override;
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Dev runs the server beside Vite on the next port; a deployed build is
    // expected to terminate both on the same host.
    const port = import.meta.env.DEV ? 5184 : location.port;
    return `${proto}//${location.hostname}${port ? `:${port}` : ''}`;
  }

  connect(identity: { name: string; avatar: number; arena: number; deck: string[]; commander: string }): void {
    this.identity = identity;
    this.wantConnection = true;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      // Already up — just refresh the identity the server has on file.
      if (this.ws.readyState === WebSocket.OPEN) this.send({ t: 'hello', ...identity });
      return;
    }
    this.open();
  }

  private open(): void {
    this.setState('connecting');
    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url());
    } catch {
      this.scheduleRetry();
      return;
    }
    this.ws = socket;

    socket.onopen = () => {
      this.retry = 0;
      this.setState('online');
      if (this.identity) this.send({ t: 'hello', ...this.identity });
    };

    socket.onmessage = (ev) => {
      let msg: ServerMessage;
      try {
        msg = JSON.parse(String(ev.data)) as ServerMessage;
      } catch {
        return;
      }
      if (msg.t === 'ping') {
        this.send({ t: 'pong' });
        return;
      }
      for (const fn of this.listeners) fn(msg);
    };

    socket.onclose = () => {
      this.ws = null;
      this.scheduleRetry();
    };

    socket.onerror = () => {
      // `onclose` always follows, so retry scheduling lives there.
    };
  }

  private scheduleRetry(): void {
    this.setState('offline');
    if (!this.wantConnection || this.retryTimer) return;
    const delay = Math.min(15000, 1000 * 2 ** this.retry);
    this.retry++;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      if (this.wantConnection) this.open();
    }, delay);
  }

  send(msg: ClientMessage): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify(msg));
    return true;
  }

  disconnect(): void {
    this.wantConnection = false;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.setState('idle');
  }
}

export const net = new NetClient();
