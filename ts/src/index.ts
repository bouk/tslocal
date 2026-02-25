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
export type {
  ClientVersion,
  DERPMap,
  DNSOSConfig,
  DNSQueryResponse,
  ExitNodeSuggestionResponse,
  FileTarget,
  LoginProfile,
  MaskedPrefs,
  NetworkLockStatus,
  NetworkProfile,
  Notify,
  OptionalFeatures,
  PeerStatus,
  PingResult,
  Prefs,
  ProfileStatus,
  ReloadConfigResponse,
  ServeConfig,
  Status,
  TailnetStatus,
  CurrentTailnet,
  UserProfile,
  WaitingFile,
  WhoIsResponse,
} from "./types.js";
export { NotifyWatchOpt } from "./types.js";
export { IPNBusWatcher } from "./ipn-bus-watcher.js";
