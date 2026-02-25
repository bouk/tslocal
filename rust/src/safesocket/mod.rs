#[cfg(target_os = "macos")]
pub mod darwin;
pub mod unix;

/// Default socket path for the current platform.
pub fn default_socket_path() -> &'static str {
    #[cfg(target_os = "macos")]
    {
        "/var/run/tailscaled.socket"
    }
    #[cfg(not(target_os = "macos"))]
    {
        "/var/run/tailscale/tailscaled.sock"
    }
}

/// The local API host header value.
pub const LOCAL_API_HOST: &str = "local-tailscaled.sock";

/// Current capability version sent in the Tailscale-Cap header.
pub const CURRENT_CAP_VERSION: u32 = 131;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_socket_path() {
        let path = default_socket_path();
        assert!(!path.is_empty());

        #[cfg(target_os = "macos")]
        assert_eq!(path, "/var/run/tailscaled.socket");

        #[cfg(target_os = "linux")]
        assert_eq!(path, "/var/run/tailscale/tailscaled.sock");
    }

    #[test]
    fn test_constants() {
        assert_eq!(LOCAL_API_HOST, "local-tailscaled.sock");
        assert_eq!(CURRENT_CAP_VERSION, 131);
    }
}
