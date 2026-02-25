use crate::safesocket;

/// Configuration for connecting to tailscaled.
#[derive(Debug, Clone)]
pub struct TransportConfig {
    /// Socket path (Unix) or pipe path (Windows).
    pub socket_path: String,
    /// TCP port for macOS token-based auth. If set, token must also be set.
    pub tcp_port: Option<u16>,
    /// Auth token for macOS TCP connection.
    pub token: Option<String>,
    /// If true, skip TCP on macOS and use socket only.
    pub use_socket_only: bool,
}

impl Default for TransportConfig {
    fn default() -> Self {
        Self {
            socket_path: safesocket::default_socket_path().to_string(),
            tcp_port: None,
            token: None,
            use_socket_only: false,
        }
    }
}

impl TransportConfig {
    /// Detect the transport configuration for the current platform.
    /// On macOS, attempts to discover TCP port and token.
    pub fn detect() -> Self {
        let mut config = Self::default();

        #[cfg(target_os = "macos")]
        {
            if let Ok((port, token)) = safesocket::darwin::local_tcp_port_and_token() {
                config.tcp_port = Some(port);
                config.token = Some(token);
            }
        }

        config
    }

    /// Whether this config uses TCP (macOS token-based auth).
    pub fn uses_tcp(&self) -> bool {
        !self.use_socket_only && self.tcp_port.is_some() && self.token.is_some()
    }

    /// Get the base URL for HTTP requests.
    pub fn base_url(&self) -> String {
        if let (Some(port), Some(_)) = (self.tcp_port, &self.token) {
            if !self.use_socket_only {
                return format!("http://127.0.0.1:{}", port);
            }
        }
        // For Unix socket connections, we use a placeholder URL;
        // the actual connection goes through the socket.
        format!("http://{}", safesocket::LOCAL_API_HOST)
    }

    /// Get the Basic Auth header value if using TCP auth.
    pub fn auth_header(&self) -> Option<String> {
        if self.uses_tcp() {
            self.token.as_ref().map(|t| {
                use std::io::Write;
                let mut buf = Vec::new();
                write!(buf, ":{}", t).unwrap();
                let encoded = base64_encode(&buf);
                format!("Basic {}", encoded)
            })
        } else {
            None
        }
    }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = TransportConfig::default();
        assert!(!config.uses_tcp());
        assert!(config.auth_header().is_none());
    }

    #[test]
    fn test_tcp_config() {
        let config = TransportConfig {
            socket_path: "/var/run/tailscaled.socket".into(),
            tcp_port: Some(8080),
            token: Some("mytoken".into()),
            use_socket_only: false,
        };
        assert!(config.uses_tcp());
        assert_eq!(config.base_url(), "http://127.0.0.1:8080");
        assert!(config.auth_header().is_some());
        let auth = config.auth_header().unwrap();
        assert!(auth.starts_with("Basic "));
    }

    #[test]
    fn test_socket_only_config() {
        let config = TransportConfig {
            socket_path: "/var/run/tailscaled.socket".into(),
            tcp_port: Some(8080),
            token: Some("mytoken".into()),
            use_socket_only: true,
        };
        assert!(!config.uses_tcp());
        assert!(config.auth_header().is_none());
    }

    #[test]
    fn test_base64_encode() {
        assert_eq!(base64_encode(b":mytoken"), "Om15dG9rZW4=");
    }
}
