import { podStore, type Connection } from "./store";

export const BAUD_RATE = 115200;

// the parts of the web serial api this file uses
export type SerialPortLike = {
  readable: ReadableStream<Uint8Array> | null;
  writable?: WritableStream<Uint8Array> | null;
  open: (options: { baudRate: number }) => Promise<void>;
  close: () => Promise<void>;
  setSignals?: (signals: { dataTerminalReady?: boolean }) => Promise<void>;
  getInfo?: () => { usbVendorId?: number; bluetoothServiceClassId?: number | string };
};

export type Transport = "bluetooth" | "usb";

// Chrome reports a Bluetooth service class for an RFCOMM port (a paired serial module such as the car kit's)
export function transportOf(port: Pick<SerialPortLike, "getInfo">): Transport {
  const info = port.getInfo?.() ?? {};
  return info.bluetoothServiceClassId !== undefined ? "bluetooth" : "usb";
}

export type SerialLike = {
  requestPort: () => Promise<SerialPortLike>;
  getPorts: () => Promise<SerialPortLike[]>;
  addEventListener: (type: "connect" | "disconnect", listener: (event: Event) => void) => void;
  removeEventListener: (type: "connect" | "disconnect", listener: (event: Event) => void) => void;
};

export function serialApi(): SerialLike | undefined {
  if (typeof navigator === "undefined") return undefined;
  return (navigator as Navigator & { serial?: SerialLike }).serial;
}

export const MAX_LINE = 4096;

const stripCR = (line: string) => line.replace(/\r$/, "");

// a line over MAX_LINE characters is dropped and counted, never buffered
export function createLineSplitter(onDrop: () => void = () => {}) {
  let rest = "";
  let skipping = false;
  let dropped = 0;
  const drop = () => {
    dropped++;
    onDrop();
  };
  return {
    push(chunk: string): string[] {
      const parts = (rest + chunk).split("\n");
      rest = parts.pop() ?? "";
      const lines: string[] = [];
      for (const part of parts) {
        if (skipping) skipping = false;
        else if (stripCR(part).length > MAX_LINE) drop();
        else lines.push(stripCR(part));
      }
      if (stripCR(rest).length > MAX_LINE) {
        if (!skipping) drop();
        skipping = true;
        rest = "";
      }
      return lines;
    },
    flush(): string[] {
      const line = stripCR(rest);
      rest = "";
      if (skipping) {
        skipping = false;
        return [];
      }
      return line ? [line] : [];
    },
    dropped: () => dropped,
  };
}

export function splitLines(onDrop?: () => void): TransformStream<string, string> {
  const splitter = createLineSplitter(onDrop);
  return new TransformStream({
    transform(chunk, controller) {
      for (const line of splitter.push(chunk)) controller.enqueue(line);
    },
    flush(controller) {
      for (const line of splitter.flush()) controller.enqueue(line);
    },
  });
}

type LinkOptions = {
  serial: SerialLike;
  onLine: (line: string) => void;
  onState: (state: Connection) => void;
  onDrop?: () => void;
  onTransport?: (transport: Transport) => void;
};

export function createSerialLink({ serial, onLine, onState, onDrop, onTransport }: LinkOptions) {
  let open: SerialPortLike | null = null;
  let reading: Promise<void> | null = null;

  async function read(port: SerialPortLike) {
    const decoder = new TextDecoderStream();
    const piped = port.readable!.pipeTo(decoder.writable as WritableStream<Uint8Array>).catch(() => {});
    const reader = decoder.readable.pipeThrough(splitLines(onDrop)).getReader();
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        onLine(value);
      }
    } catch {
      // unplugged or a read error: release the port below
    } finally {
      await reader.cancel().catch(() => {});
      await piped;
      await port.close().catch(() => {});
      if (open === port) open = null;
      onState("disconnected");
    }
  }

  async function openPort(port: SerialPortLike): Promise<boolean> {
    if (open) return true;
    onState("connecting");
    try {
      await port.open({ baudRate: BAUD_RATE });
      await port.setSignals?.({ dataTerminalReady: true });
    } catch {
      onState("disconnected");
      return false;
    }
    if (!port.readable) {
      await port.close().catch(() => {});
      onState("disconnected");
      return false;
    }
    open = port;
    onTransport?.(transportOf(port));
    onState("connected");
    reading = read(port);
    return true;
  }

  async function requestAndOpen(): Promise<boolean> {
    let port: SerialPortLike;
    try {
      port = await serial.requestPort();
    } catch {
      return false;
    }
    return openPort(port);
  }

  async function autoOpen(): Promise<boolean> {
    const [port] = await serial.getPorts().catch(() => []);
    if (!port) {
      if (!open) onState("idle");
      return false;
    }
    return openPort(port);
  }

  const onConnect = (event: Event) => {
    const port = event.target as Partial<SerialPortLike> | null;
    if (typeof port?.open === "function") void openPort(port as SerialPortLike);
    else void autoOpen();
  };

  // one command per line; false when no pod is connected or the write fails
  async function send(command: string): Promise<boolean> {
    const writable = open?.writable;
    if (!writable || writable.locked) return false;
    const writer = writable.getWriter();
    try {
      await writer.write(new TextEncoder().encode(`${command}\n`));
      return true;
    } catch {
      return false;
    } finally {
      writer.releaseLock();
    }
  }

  return {
    requestAndOpen,
    autoOpen,
    send,
    listen() {
      serial.addEventListener("connect", onConnect);
      return () => serial.removeEventListener("connect", onConnect);
    },
    closed: () => reading ?? Promise.resolve(),
    isOpen: () => open !== null,
  };
}

let link: ReturnType<typeof createSerialLink> | undefined;

function podLink() {
  const serial = serialApi();
  if (!serial) return undefined;
  link ??= createSerialLink({
    serial,
    onLine: (line) => podStore.getState().ingestLine(line, "live"),
    onState: (state) => podStore.getState().setConnection(state),
    onDrop: () => podStore.getState().countDropped(),
    onTransport: (transport) => podStore.getState().setTransport(transport),
  });
  return link;
}

export async function requestAndOpen(): Promise<boolean> {
  const current = podLink();
  if (!current) {
    podStore.getState().setConnection("unsupported");
    return false;
  }
  return current.requestAndOpen();
}

export async function sendToPod(command: string): Promise<boolean> {
  return (await podLink()?.send(command)) ?? false;
}

// reopens a port granted earlier and keeps reopening it when it is plugged back in
export function autoOpen(): () => void {
  const current = podLink();
  if (!current) {
    podStore.getState().setConnection("unsupported");
    return () => {};
  }
  void current.autoOpen();
  return current.listen();
}
