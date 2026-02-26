use std::io;
use std::path::Path;

/// Attempt to discover the macOS TCP port and token for tailscaled.
///
/// Tries two methods:
/// 1. `lsof` to find the IPNExtension process (macOS GUI app)
/// 2. Filesystem at `/Library/Tailscale/` (macOS system extension)
pub async fn local_tcp_port_and_token() -> Result<(u16, String), io::Error> {
    match read_macos_same_user_proof().await {
        Ok(result) => Ok(result),
        Err(_) => read_macsys_same_user_proof().await,
    }
}

/// Try to find port and token via lsof (macOS GUI app / IPNExtension).
async fn read_macos_same_user_proof() -> Result<(u16, String), io::Error> {
    let uid = unsafe { libc::getuid() };
    let output = tokio::process::Command::new("lsof")
        .args([
            "-n",
            "-a",
            &format!("-u{}", uid),
            "-c",
            "IPNExtension",
            "-F",
        ])
        .output()
        .await?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_lsof_output(&stdout)
}

/// Parse lsof -F output looking for sameuserproof-PORT-TOKEN.
pub(crate) fn parse_lsof_output(output: &str) -> Result<(u16, String), io::Error> {
    let needle = ".tailscale.ipn.macos/sameuserproof-";
    for line in output.lines() {
        if let Some(idx) = line.find(needle) {
            let rest = &line[idx + needle.len()..];
            if let Some(dash) = rest.find('-') {
                let port_str = &rest[..dash];
                let token = &rest[dash + 1..];
                if let Ok(port) = port_str.parse::<u16>() {
                    return Ok((port, token.to_string()));
                }
            }
        }
    }
    Err(io::Error::new(
        io::ErrorKind::NotFound,
        "sameuserproof token not found in lsof output",
    ))
}

/// Try to find port and token via filesystem (macOS system extension).
async fn read_macsys_same_user_proof() -> Result<(u16, String), io::Error> {
    read_macsys_same_user_proof_from("/Library/Tailscale").await
}

async fn read_macsys_same_user_proof_from(shared_dir: &str) -> Result<(u16, String), io::Error> {
    let port_path = Path::new(shared_dir).join("ipnport");
    let port_str = tokio::fs::read_link(&port_path)
        .await
        .map_err(|e| io::Error::new(io::ErrorKind::NotFound, e))?
        .to_string_lossy()
        .to_string();
    let port: u16 = port_str
        .parse()
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

    let token_path = Path::new(shared_dir).join(format!("sameuserproof-{}", port));
    let token = tokio::fs::read_to_string(&token_path)
        .await?
        .trim()
        .to_string();

    Ok((port, token))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_lsof_output_found() {
        let output = r#"p1234
f5
n/Users/someone/Library/Group Containers/io.tailscale.ipn.macos/sameuserproof-12345-abcdef0123456789abcd
"#;
        let (port, token) = parse_lsof_output(output).unwrap();
        assert_eq!(port, 12345);
        assert_eq!(token, "abcdef0123456789abcd");
    }

    #[test]
    fn test_parse_lsof_output_not_found() {
        let output = "p1234\nf5\nn/some/other/file\n";
        assert!(parse_lsof_output(output).is_err());
    }

    #[test]
    fn test_parse_lsof_output_empty() {
        assert!(parse_lsof_output("").is_err());
    }

    #[tokio::test]
    async fn test_read_macsys_same_user_proof_from_dir() {
        let dir = tempfile::tempdir().unwrap();
        let shared_dir = dir.path();

        // Create symlink for port
        std::os::unix::fs::symlink("8080", shared_dir.join("ipnport")).unwrap();
        // Create token file
        std::fs::write(shared_dir.join("sameuserproof-8080"), "mytoken123\n").unwrap();

        let (port, token) =
            read_macsys_same_user_proof_from(shared_dir.to_str().unwrap()).await.unwrap();
        assert_eq!(port, 8080);
        assert_eq!(token, "mytoken123");
    }

    #[tokio::test]
    async fn test_read_macsys_same_user_proof_missing() {
        let dir = tempfile::tempdir().unwrap();
        let result = read_macsys_same_user_proof_from(dir.path().to_str().unwrap()).await;
        assert!(result.is_err());
    }
}
