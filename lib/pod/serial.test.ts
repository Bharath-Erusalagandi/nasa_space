import { describe, expect, test, vi } from "vitest";
import { createLineSplitter, createSerialLink, MAX_LINE, splitLines, type SerialLike, type SerialPortLike } from "./serial";
import type { Connection } from "./store";

const bytes = (text: string) => new TextEncoder().encode(text);

describe("line splitter", () => {
  test("joins partial chunks and strips CRLF", () => {
    const splitter = createLineSplitter();
    expect(splitter.push('{"k":"hr",')).toEqual([]);
    expect(splitter.push('"v":72}\r\n{"k":"rh"')).toEqual(['{"k":"hr","v":72}']);
    expect(splitter.push(',"v":41}\r')).toEqual([]);
    expect(splitter.push("\n\r\nboot")).toEqual(['{"k":"rh","v":41}', ""]);
    expect(splitter.flush()).toEqual(["boot"]);
    expect(splitter.flush()).toEqual([]);
  });

  test("a CR split from its LF across chunks is still removed", () => {
    const splitter = createLineSplitter();
    expect(splitter.push("a\r")).toEqual([]);
    expect(splitter.push("\nb\n")).toEqual(["a", "b"]);
  });

  test("a line longer than 4096 characters is dropped and counted, in one chunk or many", () => {
    let drops = 0;
    const splitter = createLineSplitter(() => drops++);
    const long = "x".repeat(MAX_LINE + 1);
    expect(splitter.push(`${long}\nok\n`)).toEqual(["ok"]);
    expect(splitter.push(long.slice(0, 3000))).toEqual([]);
    expect(splitter.push(long.slice(3000))).toEqual([]);
    expect(splitter.push(long)).toEqual([]);
    expect(splitter.push('tail\n{"k":"rh","v":41}\n')).toEqual(['{"k":"rh","v":41}']);
    expect(splitter.push(`${"y".repeat(MAX_LINE)}\r\n`)).toEqual(["y".repeat(MAX_LINE)]);
    expect(drops).toBe(2);
    expect(splitter.dropped()).toBe(2);
  });

  test("works as a stream over one-character chunks", async () => {
    const text = '{"k":"hr","v":72}\r\n{"k":"spo2","v":98}\r\n';
    const source = new ReadableStream<string>({
      start(controller) {
        for (const ch of text) controller.enqueue(ch);
        controller.close();
      },
    });
    const lines: string[] = [];
    await source.pipeThrough(splitLines()).pipeTo(new WritableStream({ write: (line) => void lines.push(line) }));
    expect(lines).toEqual(['{"k":"hr","v":72}', '{"k":"spo2","v":98}']);
  });
});

function fakePort(chunks: string[], fail = false) {
  const calls: string[] = [];
  const queue = [...chunks];
  const port: SerialPortLike = {
    readable: new ReadableStream<Uint8Array>({
      pull(controller) {
        const chunk = queue.shift();
        if (chunk !== undefined) controller.enqueue(bytes(chunk));
        else if (fail) controller.error(new Error("device lost"));
        else controller.close();
      },
    }),
    open: async (options) => void calls.push(`open ${options.baudRate}`),
    close: async () => void calls.push("close"),
    setSignals: async (signals) => void calls.push(`dtr ${signals.dataTerminalReady}`),
  };
  return { port, calls };
}

function fakeSerial(ports: SerialPortLike[]) {
  const listeners: ((event: Event) => void)[] = [];
  const serial: SerialLike = {
    requestPort: async () => ports[0],
    getPorts: async () => ports,
    addEventListener: (_type, listener) => void listeners.push(listener),
    removeEventListener: (_type, listener) => void listeners.splice(listeners.indexOf(listener), 1),
  };
  return { serial, listeners };
}

function link(ports: SerialPortLike[]) {
  const lines: string[] = [];
  const states: Connection[] = [];
  const { serial, listeners } = fakeSerial(ports);
  const serialLink = createSerialLink({ serial, onLine: (l) => void lines.push(l), onState: (s) => void states.push(s) });
  return { serialLink, lines, states, listeners };
}

describe("serial link", () => {
  test("opens at 115200 with DTR and passes every line on", async () => {
    const { port, calls } = fakePort(['{"k":"hr","v":7', '2}\r\n{"k":"temp","v":24.1}\r\n']);
    const { serialLink, lines, states } = link([port]);
    expect(await serialLink.requestAndOpen()).toBe(true);
    await serialLink.closed();
    expect(calls.slice(0, 2)).toEqual(["open 115200", "dtr true"]);
    expect(lines).toEqual(['{"k":"hr","v":72}', '{"k":"temp","v":24.1}']);
    expect(states).toEqual(["connecting", "connected", "disconnected"]);
  });

  test("a read error disconnects and releases the port", async () => {
    const { port, calls } = fakePort(['{"k":"hr","v":72}\n'], true);
    const { serialLink, lines, states } = link([port]);
    await serialLink.autoOpen();
    await serialLink.closed();
    expect(lines).toEqual(['{"k":"hr","v":72}']);
    expect(calls).toContain("close");
    expect(states.at(-1)).toBe("disconnected");
    expect(serialLink.isOpen()).toBe(false);
  });

  test("autoOpen with no granted port stays idle", async () => {
    const { serialLink, states } = link([]);
    expect(await serialLink.autoOpen()).toBe(false);
    expect(states).toEqual(["idle"]);
  });

  test("a connect event reopens the port", async () => {
    const first = fakePort(["a\n"], true);
    const { serialLink, lines, listeners, states } = link([first.port]);
    const stop = serialLink.listen();
    await serialLink.autoOpen();
    await serialLink.closed();
    const second = fakePort(["b\n"]);
    listeners[0]({ target: second.port } as unknown as Event);
    await vi.waitFor(() => expect(states.filter((s) => s === "connected")).toHaveLength(2));
    await serialLink.closed();
    expect(lines).toEqual(["a", "b"]);
    expect(states.filter((s) => s === "connected")).toHaveLength(2);
    stop();
    expect(listeners).toHaveLength(0);
  });

  test("a port that fails to open reports disconnected", async () => {
    const { port } = fakePort([]);
    port.open = async () => {
      throw new Error("busy");
    };
    const { serialLink, states } = link([port]);
    expect(await serialLink.requestAndOpen()).toBe(false);
    expect(states).toEqual(["connecting", "disconnected"]);
  });
});

describe("serial link commands", () => {
  function writablePort() {
    const sent: string[] = [];
    let end = () => {};
    const port: SerialPortLike = {
      readable: new ReadableStream<Uint8Array>({ start: (c) => void (end = () => c.close()) }),
      writable: new WritableStream<Uint8Array>({ write: (chunk) => void sent.push(new TextDecoder().decode(chunk)) }),
      open: async () => {},
      close: async () => {},
    };
    return { port, sent, end: () => end() };
  }

  test("send writes one line to the open port and frees it for the next command", async () => {
    const { port, sent, end } = writablePort();
    const { serialLink } = link([port]);
    expect(await serialLink.send("dispatch")).toBe(false);
    await serialLink.requestAndOpen();
    expect(await serialLink.send("dispatch")).toBe(true);
    expect(await serialLink.send("stop")).toBe(true);
    expect(sent).toEqual(["dispatch\n", "stop\n"]);
    end();
    await serialLink.closed();
    expect(await serialLink.send("nod")).toBe(false);
    expect(sent).toHaveLength(2);
  });

  test("send reports false on a port that cannot be written", async () => {
    const { port, end } = writablePort();
    port.writable = null;
    const { serialLink } = link([port]);
    await serialLink.requestAndOpen();
    expect(await serialLink.send("dispatch")).toBe(false);
    end();
    await serialLink.closed();
  });
});
