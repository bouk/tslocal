use crate::safesocket;
use hyper_util::client::legacy::connect::Connected;
use hyper_util::rt::TokioIo;
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

/// Configuration for connecting to tailscaled.
///
/// Matches Go's `local.Client` fields: `Socket` and `UseSocketOnly`.
#[derive(Debug, Clone)]
pub struct TransportConfig {
    /// Socket path (Unix) or pipe path (Windows).
    /// If empty, a platform-specific default is used.
    pub socket_path: String,
    /// If true, only connect via the Unix socket and skip TCP fallback
    /// mechanisms used on macOS when connecting to the GUI client.
    pub use_socket_only: bool,
}

impl Default for TransportConfig {
    fn default() -> Self {
        Self {
            socket_path: safesocket::default_socket_path().to_string(),
            use_socket_only: false,
        }
    }
}

/// Discover the current TCP port and token.
/// Returns (port, token) if TCP should be used, None for Unix socket.
pub(crate) async fn resolve_port_and_token(use_socket_only: bool) -> Option<(u16, String)> {
    if use_socket_only {
        return None;
    }

    #[cfg(target_os = "macos")]
    {
        if let Ok((port, token)) = safesocket::darwin::local_tcp_port_and_token().await {
            return Some((port, token));
        }
    }

    None
}

/// Compute a Basic Auth header value for the given token.
pub(crate) fn auth_header_for_token(token: &str) -> String {
    use std::io::Write;
    let mut buf = Vec::new();
    _ = write!(buf, ":{token}");
    let encoded = base64_encode(&buf);
    format!("Basic {encoded}")
}

fn base64_encode(data: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::new();
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        result.push(CHARS[((triple >> 18) & 0x3F) as usize] as char);
        result.push(CHARS[((triple >> 12) & 0x3F) as usize] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((triple >> 6) & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(CHARS[(triple & 0x3F) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}

/// Connection type that wraps either a TCP or Unix stream.
pub(crate) enum TailscaleStream {
    Tcp(TokioIo<tokio::net::TcpStream>),
    Unix(TokioIo<tokio::net::UnixStream>),
}

impl hyper::rt::Read for TailscaleStream {
    fn poll_read(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        buf: hyper::rt::ReadBufCursor<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        match self.get_mut() {
            TailscaleStream::Tcp(s) => Pin::new(s).poll_read(cx, buf),
            TailscaleStream::Unix(s) => Pin::new(s).poll_read(cx, buf),
        }
    }
}

impl hyper::rt::Write for TailscaleStream {
    fn poll_write(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        buf: &[u8],
    ) -> Poll<Result<usize, std::io::Error>> {
        match self.get_mut() {
            TailscaleStream::Tcp(s) => Pin::new(s).poll_write(cx, buf),
            TailscaleStream::Unix(s) => Pin::new(s).poll_write(cx, buf),
        }
    }

    fn poll_flush(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        match self.get_mut() {
            TailscaleStream::Tcp(s) => Pin::new(s).poll_flush(cx),
            TailscaleStream::Unix(s) => Pin::new(s).poll_flush(cx),
        }
    }

    fn poll_shutdown(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        match self.get_mut() {
            TailscaleStream::Tcp(s) => Pin::new(s).poll_shutdown(cx),
            TailscaleStream::Unix(s) => Pin::new(s).poll_shutdown(cx),
        }
    }
}

impl hyper_util::client::legacy::connect::Connection for TailscaleStream {
    fn connected(&self) -> Connected {
        Connected::new()
    }
}

/// Hyper connector that discovers tailscaled's TCP port or falls back to Unix socket.
///
/// On each new connection, calls `resolve_port_and_token` to decide whether to
/// connect via TCP (macOS) or Unix socket, matching Go's `defaultDialer`.
#[derive(Clone)]
pub(crate) struct TailscaleConnector {
    socket_path: String,
    use_socket_only: bool,
}

impl TailscaleConnector {
    pub fn new(config: &TransportConfig) -> Self {
        Self {
            socket_path: config.socket_path.clone(),
            use_socket_only: config.use_socket_only,
        }
    }
}

impl tower_service::Service<hyper::Uri> for TailscaleConnector {
    type Response = TailscaleStream;
    type Error = std::io::Error;
    type Future = Pin<Box<dyn Future<Output = Result<TailscaleStream, std::io::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, _uri: hyper::Uri) -> Self::Future {
        let socket_path = self.socket_path.clone();
        let use_socket_only = self.use_socket_only;
        Box::pin(async move {
            if let Some((port, _)) = resolve_port_and_token(use_socket_only).await {
                let stream = tokio::net::TcpStream::connect(("127.0.0.1", port)).await?;
                Ok(TailscaleStream::Tcp(TokioIo::new(stream)))
            } else {
                let stream = tokio::net::UnixStream::connect(&socket_path).await?;
                Ok(TailscaleStream::Unix(TokioIo::new(stream)))
            }
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_default_config() {
        // On non-macOS, or when daemon isn't running, returns None
        // On macOS with daemon running, may return Some
        let _ = resolve_port_and_token(false).await;
    }

    #[tokio::test]
    async fn test_socket_only_skips_discovery() {
        assert!(resolve_port_and_token(true).await.is_none());
    }

    #[test]
    fn test_auth_header_for_token() {
        let header = auth_header_for_token("mytoken");
        assert!(header.starts_with("Basic "));
    }

    #[test]
    fn test_base64_encode() {
        assert_eq!(base64_encode(b":mytoken"), "Om15dG9rZW4=");
    }
}
