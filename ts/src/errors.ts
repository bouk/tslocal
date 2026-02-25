/** Base error for all Tailscale Local API errors. */
export class TailscaleError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TailscaleError";
  }
}

/** Raised when the server returns HTTP 403. */
export class AccessDeniedError extends TailscaleError {
  constructor(message: string) {
    super(`Access denied: ${message}`);
    this.name = "AccessDeniedError";
  }
}

/** Raised when the server returns HTTP 412. */
export class PreconditionsFailedError extends TailscaleError {
  constructor(message: string) {
    super(`Preconditions failed: ${message}`);
    this.name = "PreconditionsFailedError";
  }
}

/** Raised when a WhoIs lookup returns HTTP 404. */
export class PeerNotFoundError extends TailscaleError {
  constructor(message: string) {
    super(`Peer not found: ${message}`);
    this.name = "PeerNotFoundError";
  }
}

/** Raised when the connection to tailscaled fails. */
export class ConnectionError extends TailscaleError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}

/** Raised when tailscaled is not running. */
export class DaemonNotRunningError extends ConnectionError {
  constructor(message: string) {
    super(message);
    this.name = "DaemonNotRunningError";
  }
}

/** Raised for unexpected HTTP status codes. */
export class HttpError extends TailscaleError {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(`HTTP ${status}: ${message}`);
    this.name = "HttpError";
    this.status = status;
  }
}

/** Extract error message from a JSON body like Go's errorMessageFromBody. */
export function errorMessageFromBody(body: string): string | undefined {
  try {
    const data = JSON.parse(body);
    return data?.error;
  } catch {
    return undefined;
  }
}
