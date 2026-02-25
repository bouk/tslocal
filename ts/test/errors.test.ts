import { describe, expect, it } from "vitest";
import {
  AccessDeniedError,
  ConnectionError,
  DaemonNotRunningError,
  HttpError,
  PeerNotFoundError,
  PreconditionsFailedError,
  TailscaleError,
  errorMessageFromBody,
} from "../src/errors.js";

describe("error hierarchy", () => {
  it("AccessDeniedError extends TailscaleError", () => {
    const err = new AccessDeniedError("not authorized");
    expect(err).toBeInstanceOf(TailscaleError);
    expect(err).toBeInstanceOf(AccessDeniedError);
    expect(err.message).toContain("not authorized");
  });

  it("PreconditionsFailedError extends TailscaleError", () => {
    const err = new PreconditionsFailedError("state mismatch");
    expect(err).toBeInstanceOf(TailscaleError);
    expect(err.message).toContain("state mismatch");
  });

  it("PeerNotFoundError extends TailscaleError", () => {
    const err = new PeerNotFoundError("1.2.3.4");
    expect(err).toBeInstanceOf(TailscaleError);
    expect(err.message).toContain("1.2.3.4");
  });

  it("DaemonNotRunningError extends ConnectionError", () => {
    const err = new DaemonNotRunningError("not running");
    expect(err).toBeInstanceOf(ConnectionError);
    expect(err).toBeInstanceOf(TailscaleError);
  });

  it("HttpError has status code", () => {
    const err = new HttpError(500, "internal error");
    expect(err).toBeInstanceOf(TailscaleError);
    expect(err.status).toBe(500);
    expect(err.message).toContain("500");
  });
});

describe("errorMessageFromBody", () => {
  it("extracts error from JSON", () => {
    expect(errorMessageFromBody('{"error": "something went wrong"}')).toBe(
      "something went wrong",
    );
  });

  it("returns undefined for missing error field", () => {
    expect(errorMessageFromBody("{}")).toBeUndefined();
  });

  it("returns undefined for invalid JSON", () => {
    expect(errorMessageFromBody("not json")).toBeUndefined();
  });
});
