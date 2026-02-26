import { execFile } from "node:child_process";
import { readFile, readlink } from "node:fs/promises";
import { platform } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";

export const LOCAL_API_HOST = "local-tailscaled.sock";
export const CURRENT_CAP_VERSION = 131;

export interface PortAndToken {
  port: number;
  token: string;
}

/** Return the default socket path for the current platform. */
export function defaultSocketPath(): string {
  if (platform() === "darwin") {
    return "/var/run/tailscaled.socket";
  }
  // Linux and other Unix
  return "/var/run/tailscale/tailscaled.sock";
}

/** Attempt to discover macOS TCP port and token for tailscaled. */
export async function localTcpPortAndToken(): Promise<PortAndToken | undefined> {
  if (platform() !== "darwin") {
    return undefined;
  }

  // Try lsof method first (macOS GUI app)
  const result = await readMacosSameUserProof();
  if (result) return result;

  // Try filesystem method (macOS system extension)
  return readMacsysSameUserProof();
}

const execFileP = promisify(execFile);

async function readMacosSameUserProof(): Promise<PortAndToken | undefined> {
  try {
    const uid = process.getuid?.();
    if (uid === undefined) return undefined;

    const { stdout: output } = await execFileP("lsof", [
      "-n",
      "-a",
      `-u${uid}`,
      "-c",
      "IPNExtension",
      "-F",
    ]);
    return parseLsofOutput(output);
  } catch {
    return undefined;
  }
}

/** Parse lsof -F output looking for sameuserproof-PORT-TOKEN. */
export function parseLsofOutput(output: string): PortAndToken | undefined {
  const needle = ".tailscale.ipn.macos/sameuserproof-";
  for (const line of output.split("\n")) {
    const idx = line.indexOf(needle);
    if (idx === -1) continue;
    const rest = line.slice(idx + needle.length);
    const dash = rest.indexOf("-");
    if (dash === -1) continue;
    const portStr = rest.slice(0, dash);
    const token = rest.slice(dash + 1);
    const port = parseInt(portStr, 10);
    if (!isNaN(port)) {
      return { port, token };
    }
  }
  return undefined;
}

async function readMacsysSameUserProof(
  sharedDir = "/Library/Tailscale",
): Promise<PortAndToken | undefined> {
  try {
    const portPath = join(sharedDir, "ipnport");
    const portStr = await readlink(portPath, "utf-8");
    const port = parseInt(portStr, 10);
    if (isNaN(port)) return undefined;
    const tokenPath = join(sharedDir, `sameuserproof-${port}`);
    const tokenRaw = await readFile(tokenPath, "utf-8");
    const token = tokenRaw.trim();
    return { port, token };
  } catch {
    return undefined;
  }
}
