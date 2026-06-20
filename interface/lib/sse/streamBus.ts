// Mini-EventBus fuers Streaming. Die <StreamingBubble> subscribed darauf via
// useSyncExternalStore, sodass NUR sie bei jedem llm_delta re-rendert — nicht
// die gesamte MessageList. Der Buffer lebt als Ref, das State (subscriberCount,
// snapshot) wird ueber den Subscribe-Mechanismus verteilt.

type Listener = () => void;

interface Bus {
  text: string;
  caret: boolean;
  listeners: Set<Listener>;
}

const bus: Bus = { text: "", caret: false, listeners: new Set() };

export const streamBus = {
  subscribe(cb: Listener): () => void {
    bus.listeners.add(cb);
    return () => bus.listeners.delete(cb);
  },
  getSnapshot(): { text: string; caret: boolean } {
    // useSyncExternalStore vergleicht per Identitaet — wir geben jedes Mal
    // ein neues Objekt zurueck, aber NUR wenn sich text/caret geaendert haben
    // (siehe append/reset). Snapshot-Caching laeuft hier:
    return cachedSnapshot;
  },
  append(delta: string) {
    if (!delta) return;
    bus.text += delta;
    cachedSnapshot = { text: bus.text, caret: bus.caret };
    bus.listeners.forEach((l) => l());
  },
  reset(caret: boolean) {
    bus.text = "";
    bus.caret = caret;
    cachedSnapshot = { text: "", caret };
    bus.listeners.forEach((l) => l());
  },
  setCaret(on: boolean) {
    if (bus.caret === on) return;
    bus.caret = on;
    cachedSnapshot = { text: bus.text, caret: on };
    bus.listeners.forEach((l) => l());
  },
  current(): string {
    return bus.text;
  },
};

let cachedSnapshot: { text: string; caret: boolean } = { text: "", caret: false };
