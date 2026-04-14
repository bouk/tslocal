export { Client } from "./client.js";
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

import type { Node as NodeType } from "./types.js";
export type Node = NodeType;
export const Node = {
  /** Reports whether the node has any ACL tags. */
  isTagged(node: NodeType): boolean {
    return node.Tags.length > 0;
  },
};
