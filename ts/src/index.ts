export { LocalClient } from "./client.js";
export {
  TailscaleError,
  AccessDeniedError,
  PreconditionsFailedError,
  PeerNotFoundError,
  ConnectionError,
  DaemonNotRunningError,
  HttpError,
} from "./errors.js";
export {
  ClientVersionSchema,
  CurrentTailnetSchema,
  PeerStatusSchema,
  ServeConfigSchema,
  StatusSchema,
  TailnetStatusSchema,
  UserProfileSchema,
  WhoIsResponseSchema,
  type ClientVersion,
  type CurrentTailnet,
  type PeerStatus,
  type ServeConfig,
  type Status,
  type TailnetStatus,
  type UserProfile,
  type WhoIsResponse,
} from "./types.js";
