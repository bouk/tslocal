import type { Readable } from "node:stream";
import type { Notify } from "./types.js";

/**
 * Async iterator over IPN bus notifications.
 *
 * Usage:
 *   for await (const notify of watcher) {
 *     console.log(notify.State);
 *   }
 */
export class IPNBusWatcher implements AsyncIterable<Notify> {
  private reader: Readable;
  private buffer = "";
  private closed = false;

  constructor(reader: Readable) {
    this.reader = reader;
  }

  async next(): Promise<Notify> {
    while (true) {
      const newlineIdx = this.buffer.indexOf("\n");
      if (newlineIdx !== -1) {
        const line = this.buffer.slice(0, newlineIdx);
        this.buffer = this.buffer.slice(newlineIdx + 1);
        if (line.trim()) {
          return JSON.parse(line);
        }
        continue;
      }

      if (this.closed) {
        throw new Error("watcher closed");
      }

      const chunk = await new Promise<string | null>((resolve, reject) => {
        const onData = (data: Buffer) => {
          cleanup();
          resolve(data.toString("utf-8"));
        };
        const onEnd = () => {
          cleanup();
          resolve(null);
        };
        const onError = (err: Error) => {
          cleanup();
          reject(err);
        };
        const cleanup = () => {
          this.reader.removeListener("data", onData);
          this.reader.removeListener("end", onEnd);
          this.reader.removeListener("error", onError);
        };
        this.reader.once("data", onData);
        this.reader.once("end", onEnd);
        this.reader.once("error", onError);
      });

      if (chunk === null) {
        throw new Error("stream ended");
      }
      this.buffer += chunk;
    }
  }

  close(): void {
    this.closed = true;
    this.reader.destroy();
  }

  async *[Symbol.asyncIterator](): AsyncIterator<Notify> {
    try {
      while (!this.closed) {
        yield await this.next();
      }
    } catch {
      // Stream ended or closed
    }
  }
}
