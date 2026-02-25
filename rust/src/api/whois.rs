use crate::client::Client;
use crate::error::Error;
use crate::types::WhoIsResponse;

impl Client {
    /// Look up the owner of an IP address, IP:port, or node key.
    ///
    /// Returns `Error::PeerNotFound` if the peer is not found (HTTP 404).
    pub async fn who_is(&self, remote_addr: &str) -> Result<WhoIsResponse, Error> {
        let (status, body) = self
            .do_request(
                "GET",
                &format!(
                    "/localapi/v0/whois?addr={}",
                    crate::urlencode(remote_addr)
                ),
                None,
            )
            .await?;
        if status == 404 {
            return Err(Error::PeerNotFound {
                message: remote_addr.to_string(),
            });
        }
        if !(200..300).contains(&status) {
            let msg = crate::error::error_message_from_body(&body)
                .unwrap_or_else(|| String::from_utf8_lossy(&body).to_string());
            return match status {
                403 => Err(Error::AccessDenied { message: msg }),
                412 => Err(Error::PreconditionsFailed { message: msg }),
                _ => Err(Error::Http {
                    status,
                    message: msg,
                }),
            };
        }
        Ok(serde_json::from_slice(&body)?)
    }

    /// Look up a peer by node key.
    pub async fn who_is_node_key(&self, node_key: &str) -> Result<WhoIsResponse, Error> {
        self.who_is(node_key).await
    }

    /// Look up the owner of an IP address with a specific protocol.
    ///
    /// The `proto` parameter should be "tcp" or "udp".
    pub async fn who_is_proto(
        &self,
        proto: &str,
        remote_addr: &str,
    ) -> Result<WhoIsResponse, Error> {
        let (status, body) = self
            .do_request(
                "GET",
                &format!(
                    "/localapi/v0/whois?proto={}&addr={}",
                    crate::urlencode(proto),
                    crate::urlencode(remote_addr)
                ),
                None,
            )
            .await?;
        if status == 404 {
            return Err(Error::PeerNotFound {
                message: remote_addr.to_string(),
            });
        }
        if !(200..300).contains(&status) {
            let msg = crate::error::error_message_from_body(&body)
                .unwrap_or_else(|| String::from_utf8_lossy(&body).to_string());
            return match status {
                403 => Err(Error::AccessDenied { message: msg }),
                412 => Err(Error::PreconditionsFailed { message: msg }),
                _ => Err(Error::Http {
                    status,
                    message: msg,
                }),
            };
        }
        Ok(serde_json::from_slice(&body)?)
    }
}
