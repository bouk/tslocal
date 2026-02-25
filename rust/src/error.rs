use thiserror::Error;

/// Root error type for the Tailscale Local API client.
#[derive(Error, Debug)]
pub enum Error {
    #[error("access denied: {message}")]
    AccessDenied { message: String },

    #[error("preconditions failed: {message}")]
    PreconditionsFailed { message: String },

    #[error("peer not found: {message}")]
    PeerNotFound { message: String },

    #[error("connection error: {message}")]
    Connection { message: String },

    #[error("daemon not running")]
    DaemonNotRunning,

    #[error("HTTP error {status}: {message}")]
    Http { status: u16, message: String },

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("{0}")]
    Other(String),
}

impl Error {
    pub fn is_access_denied(&self) -> bool {
        matches!(self, Error::AccessDenied { .. })
    }

    pub fn is_preconditions_failed(&self) -> bool {
        matches!(self, Error::PreconditionsFailed { .. })
    }

    pub fn is_peer_not_found(&self) -> bool {
        matches!(self, Error::PeerNotFound { .. })
    }

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
