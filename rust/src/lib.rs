#![deny(missing_docs)]
#![deny(clippy::all)]

//! Client library for the Tailscale Local API.

mod client;
mod error;
mod safesocket;
mod transport;
#[allow(missing_docs)]
mod types;
mod types_ext;

pub use client::Client;
pub use error::Error;
pub use transport::TransportConfig;
pub use types::*;

/// URL-encode a string for use in query parameters.
pub(crate) fn urlencode(s: &str) -> String {
    url::form_urlencoded::byte_serialize(s.as_bytes()).collect()
}
