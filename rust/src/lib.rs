pub mod api;
pub mod client;
pub mod error;
pub mod safesocket;
pub mod transport;
pub mod types;

// Re-export the most commonly used types at the crate root.
pub use client::Client;
pub use error::Error;
pub use types::{PeerStatus, ServeConfig, Status, WhoIsResponse};

/// URL-encode a string for use in query parameters.
pub(crate) fn urlencode(s: &str) -> String {
    url::form_urlencoded::byte_serialize(s.as_bytes()).collect()
}
