import { describe, expect, it } from "vitest";
import {
  CURRENT_CAP_VERSION,
  LOCAL_API_HOST,
  defaultSocketPath,
  parseLsofOutput,
} from "../src/safesocket.js";
import { platform } from "node:os";

describe("constants", () => {
  it("LOCAL_API_HOST", () => {
    expect(LOCAL_API_HOST).toBe("local-tailscaled.sock");
  });

  it("CURRENT_CAP_VERSION", () => {
    expect(CURRENT_CAP_VERSION).toBe(138);
  });
});

describe("defaultSocketPath", () => {
  it("returns non-empty path", () => {
    expect(defaultSocketPath()).toBeTruthy();
  });

  it("returns platform-appropriate path", () => {
    const path = defaultSocketPath();
    if (platform() === "darwin") {
      expect(path).toBe("/var/run/tailscaled.socket");
    } else if (platform() === "linux") {
      expect(path).toBe("/var/run/tailscale/tailscaled.sock");
    }
  });
});

describe("parseLsofOutput", () => {
  it("finds sameuserproof in lsof output", () => {
    const output = [
      "p1234",
      "f5",
      "n/Users/someone/Library/Group Containers/io.tailscale.ipn.macos/sameuserproof-12345-abcdef0123456789abcd",
    ].join("\n");

    const result = parseLsofOutput(output);
    expect(result).toBeDefined();
    expect(result!.port).toBe(12345);
    expect(result!.token).toBe("abcdef0123456789abcd");
  });

  it("returns undefined when not found", () => {
    expect(parseLsofOutput("p1234\nf5\nn/some/file")).toBeUndefined();
  });

  it("returns undefined for empty output", () => {
    expect(parseLsofOutput("")).toBeUndefined();
  });
});
