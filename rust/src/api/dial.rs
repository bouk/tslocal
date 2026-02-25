use crate::client::Client;
use crate::error::{error_message_from_body, Error};
use http_body_util::BodyExt;
use hyper_util::rt::TokioIo;

impl Client {
    /// Connect to the host's port via Tailscale over TCP.
    ///
    /// The host may be a base DNS name (resolved from the netmap inside
    /// tailscaled), a FQDN, or an IP address.
    pub async fn dial_tcp(
        &self,
        host: &str,
        port: u16,
    ) -> Result<TokioIo<hyper::upgrade::Upgraded>, Error> {
        self.user_dial("tcp", host, port).await
    }

    /// Connect to the host's port via Tailscale for the given network.
    ///
    /// The host may be a base DNS name (resolved from the netmap inside
    /// tailscaled), a FQDN, or an IP address.
    pub async fn user_dial(
        &self,
        network: &str,
        host: &str,
        port: u16,
    ) -> Result<TokioIo<hyper::upgrade::Upgraded>, Error> {
        let req = self.build_request_with_headers(
            "POST",
            "/localapi/v0/dial",
            None,
            &[
                ("Upgrade", "ts-dial"),
                ("Connection", "upgrade"),
                ("Dial-Host", host),
                ("Dial-Port", &port.to_string()),
                ("Dial-Network", network),
            ],
        )?;

        let resp = self.send_request(req).await?;
        let status = resp.status().as_u16();

        if status != 101 {
            let body = resp
                .into_body()
                .collect()
                .await
                .map_err(|e| {
                    Error::Io(std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))
                })?
                .to_bytes();
            let msg = error_message_from_body(&body)
                .unwrap_or_else(|| format!("unexpected HTTP response: {}", status));
            return Err(Error::Http {
                status,
                message: msg,
            });
        }

        let upgraded = hyper::upgrade::on(resp)
            .await
            .map_err(|e| Error::Connection {
                message: format!("upgrade failed: {}", e),
            })?;

        Ok(TokioIo::new(upgraded))
    }
}
