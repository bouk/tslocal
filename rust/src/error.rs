use thiserror::Error;

/// Root error type for the Tailscale Local API client.
#[derive(Error, Debug)]
pub enum Error {
    /// The server returned HTTP 403.
    #[error("access denied: {message}")]
    AccessDenied {
        /// The error message from the server.
        message: String,
    },

    /// The server returned HTTP 412.
    #[error("preconditions failed: {message}")]
    PreconditionsFailed {
        /// The error message from the server.
        message: String,
    },

    /// A WhoIs lookup returned HTTP 404.
    #[error("peer not found: {message}")]
    PeerNotFound {
        /// The address or key that was not found.
        message: String,
    },

    /// Failed to connect to tailscaled.
    #[error("connection error: {message}")]
    Connection {
        /// The underlying connection error message.
        message: String,
    },

    /// The tailscale daemon is not running.
    #[error("daemon not running")]
    DaemonNotRunning,

    /// An unexpected HTTP status code was returned.
    #[error("HTTP error {status}: {message}")]
    Http {
        /// The HTTP status code.
        status: u16,
        /// The error message from the server.
        message: String,
    },

    /// JSON serialization or deserialization failed.
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    /// An I/O error occurred.
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// An error that doesn't fit other categories.
    #[error("{0}")]
    Other(String),
}

impl Error {
    /// Returns `true` if this is an [`Error::AccessDenied`] error.
    pub fn is_access_denied(&self) -> bool {
        matches!(self, Error::AccessDenied { .. })
    }

    /// Returns `true` if this is an [`Error::PreconditionsFailed`] error.
    pub fn is_preconditions_failed(&self) -> bool {
        matches!(self, Error::PreconditionsFailed { .. })
    }

    /// Returns `true` if this is an [`Error::PeerNotFound`] error.
    pub fn is_peer_not_found(&self) -> bool {
        matches!(self, Error::PeerNotFound { .. })
    }

    /// Returns `true` if this is a connection-related error.
    pub fn is_connection_error(&self) -> bool {
        matches!(self, Error::Connection { .. } | Error::DaemonNotRunning)
    }
}

/// Extract error message from a JSON body like Go's `errorMessageFromBody`.
pub(crate) fn error_message_from_body(body: &[u8]) -> Option<String> {
    #[derive(serde::Deserialize)]
    struct ErrorBody {
        error: Option<String>,
    }
    serde_json::from_slice::<ErrorBody>(body)
        .ok()
        .and_then(|b| b.error)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_access_denied_error() {
        let err = Error::AccessDenied {
            message: "not authorized".into(),
        };
        assert!(err.is_access_denied());
        assert!(!err.is_peer_not_found());
        assert_eq!(err.to_string(), "access denied: not authorized");
    }

    #[test]
    fn test_preconditions_failed_error() {
        let err = Error::PreconditionsFailed {
            message: "state mismatch".into(),
        };
        assert!(err.is_preconditions_failed());
        assert!(!err.is_access_denied());
        assert_eq!(err.to_string(), "preconditions failed: state mismatch");
    }

    #[test]
    fn test_peer_not_found_error() {
        let err = Error::PeerNotFound {
            message: "no such peer".into(),
        };
        assert!(err.is_peer_not_found());
        assert_eq!(err.to_string(), "peer not found: no such peer");
    }

    #[test]
    fn test_connection_error() {
        let err = Error::Connection {
            message: "refused".into(),
        };
        assert!(err.is_connection_error());

        let err2 = Error::DaemonNotRunning;
        assert!(err2.is_connection_error());
    }

    #[test]
    fn test_error_message_from_body() {
        let body = br#"{"error": "something went wrong"}"#;
        assert_eq!(
            error_message_from_body(body),
            Some("something went wrong".into())
        );

        let bad = b"not json";
        assert_eq!(error_message_from_body(bad), None);

        let empty = br#"{}"#;
        assert_eq!(error_message_from_body(empty), None);
    }
}
