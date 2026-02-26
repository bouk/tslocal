use crate::error::{error_message_from_body, Error};
use crate::safesocket;
use crate::transport::{TailscaleConnector, TransportConfig, auth_header_for_token, resolve_port_and_token};
use crate::types::{ServeConfig, Status, WhoIsResponse};
use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::{Request, Response};
use hyper_util::client::legacy::Client as HyperClient;
use hyper_util::rt::TokioExecutor;

/// Client for the Tailscale Local API.
///
/// Connections are pooled and reused via hyper's connection management.
/// TCP port and auth token are discovered per-request (matching Go's behavior),
/// so the client adapts to daemon restarts and late starts.
pub struct Client {
    config: TransportConfig,
    client: HyperClient<TailscaleConnector, Full<Bytes>>,
}

impl Client {
    /// Create a new client with default transport settings.
    ///
    /// Port and token are discovered per-request, so the client works even if
    /// the daemon isn't running at creation time.
    pub fn new() -> Self {
        Self::with_config(TransportConfig::default())
    }

    /// Create a new client with explicit transport configuration.
    pub fn with_config(config: TransportConfig) -> Self {
        let connector = TailscaleConnector::new(&config);
        let client = HyperClient::builder(TokioExecutor::new())
            .pool_idle_timeout(std::time::Duration::from_secs(60))
            .build(connector);
        Self { config, client }
    }

    /// Send an HTTP request to the local API and return the response.
    ///
    /// Discovers TCP token per-request for the auth header (the connector
    /// independently discovers port for connection routing).
    pub(crate) async fn send_request(
        &self,
        req: Request<Full<Bytes>>,
    ) -> Result<Response<Incoming>, Error> {
        let req = if let Some((_, ref token)) = resolve_port_and_token(self.config.use_socket_only).await {
            let (mut parts, body) = req.into_parts();
            parts.headers.insert(
                hyper::header::AUTHORIZATION,
                auth_header_for_token(token).parse().map_err(|e: hyper::header::InvalidHeaderValue| Error::Other(e.to_string()))?,
            );
            Request::from_parts(parts, body)
        } else {
            req
        };

        self.client.request(req).await.map_err(|e| Error::Connection {
            message: e.to_string(),
        })
    }

    /// Build an HTTP request with standard headers.
    pub(crate) fn build_request(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<Request<Full<Bytes>>, Error> {
        let uri = hyper::Uri::builder()
            .scheme("http")
            .authority(safesocket::LOCAL_API_HOST)
            .path_and_query(path)
            .build()
            .map_err(|e| Error::Other(e.to_string()))?;

        let body_bytes = body.map(Bytes::copy_from_slice).unwrap_or_default();

        Request::builder()
            .method(method)
            .uri(uri)
            .header("Host", safesocket::LOCAL_API_HOST)
            .header("Tailscale-Cap", safesocket::CURRENT_CAP_VERSION.to_string())
            .body(Full::new(body_bytes))
            .map_err(|e| Error::Other(e.to_string()))
    }

    /// Send a pre-built request and return status + body.
    pub(crate) async fn send_request_body(
        &self,
        req: Request<Full<Bytes>>,
    ) -> Result<(u16, Vec<u8>), Error> {
        let resp = self.send_request(req).await?;
        let status = resp.status().as_u16();
        let body = resp
            .into_body()
            .collect()
            .await
            .map_err(|e| Error::Io(std::io::Error::new(std::io::ErrorKind::Other, e.to_string())))?
            .to_bytes()
            .to_vec();
        Ok((status, body))
    }

    /// Send a request and return status + body.
    pub(crate) async fn do_request(
        &self,
        method: &str,
        path: &str,
    ) -> Result<(u16, Vec<u8>), Error> {
        let req = self.build_request(method, path, None)?;
        self.send_request_body(req).await
    }

    /// Send a pre-built request and map non-2xx status codes to errors.
    pub(crate) async fn do_request_nice_req(
        &self,
        req: Request<Full<Bytes>>,
    ) -> Result<Vec<u8>, Error> {
        let (status, body) = self.send_request_body(req).await?;
        if (200..300).contains(&status) {
            return Ok(body);
        }

        let msg = error_message_from_body(&body)
            .unwrap_or_else(|| String::from_utf8_lossy(&body).to_string());

        match status {
            403 => Err(Error::AccessDenied { message: msg }),
            412 => Err(Error::PreconditionsFailed { message: msg }),
            _ => Err(Error::Http {
                status,
                message: msg,
            }),
        }
    }

    /// Send a request and map non-2xx status codes to errors (like `doLocalRequestNiceError`).
    pub(crate) async fn do_request_nice(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<Vec<u8>, Error> {
        let req = self.build_request(method, path, body)?;
        self.do_request_nice_req(req).await
    }

    /// GET request expecting 2xx response.
    pub(crate) async fn get200(&self, path: &str) -> Result<Vec<u8>, Error> {
        self.do_request_nice("GET", path, None).await
    }

}

impl Default for Client {
    fn default() -> Self {
        Self::new()
    }
}

/// Local API methods.
impl Client {
    /// Get the current tailscaled status.
    pub async fn status(&self) -> Result<Status, Error> {
        let body = self.get200("/localapi/v0/status").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get the current tailscaled status without peer information.
    pub async fn status_without_peers(&self) -> Result<Status, Error> {
        let body = self.get200("/localapi/v0/status?peers=false").await?;
        Ok(serde_json::from_slice(&body)?)
    }

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
            )
            .await?;
        if status == 404 {
            return Err(Error::PeerNotFound {
                message: remote_addr.to_string(),
            });
        }
        if !(200..300).contains(&status) {
            let msg = error_message_from_body(&body)
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
            )
            .await?;
        if status == 404 {
            return Err(Error::PeerNotFound {
                message: remote_addr.to_string(),
            });
        }
        if !(200..300).contains(&status) {
            let msg = error_message_from_body(&body)
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

    /// Get a TLS certificate and private key for the given domain.
    /// Returns (cert_pem, key_pem).
    pub async fn cert_pair(&self, domain: &str) -> Result<(Vec<u8>, Vec<u8>), Error> {
        self.cert_pair_with_validity(domain, 0).await
    }

    /// Get a TLS certificate with minimum validity duration (in seconds).
    /// Returns (cert_pem, key_pem).
    pub async fn cert_pair_with_validity(
        &self,
        domain: &str,
        min_validity_secs: u64,
    ) -> Result<(Vec<u8>, Vec<u8>), Error> {
        let path = format!(
            "/localapi/v0/cert/{}?type=pair&min_validity={}s",
            crate::urlencode(domain),
            min_validity_secs
        );
        let body = self.get200(&path).await?;

        // Response is key PEM then cert PEM, separated by "--\n--"
        let delimiter = b"--\n--";
        let pos = body
            .windows(delimiter.len())
            .position(|w| w == delimiter)
            .ok_or_else(|| Error::Other("unexpected cert response: no delimiter".into()))?;
        let split = pos + 3; // include "--\n"
        let key_pem = body[..split].to_vec();
        let cert_pem = body[split..].to_vec();
        Ok((cert_pem, key_pem))
    }

    /// Get the current serve config.
    ///
    /// The returned `ServeConfig` has its `e_tag` field populated from the
    /// HTTP `Etag` response header.
    pub async fn get_serve_config(&self) -> Result<ServeConfig, Error> {
        let req = self.build_request("GET", "/localapi/v0/serve-config", None)?;
        let resp = self.send_request(req).await?;
        let status = resp.status().as_u16();
        let etag = resp
            .headers()
            .get("Etag")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("")
            .to_string();
        let body = resp
            .into_body()
            .collect()
            .await
            .map_err(|e| {
                Error::Io(std::io::Error::new(
                    std::io::ErrorKind::Other,
                    e.to_string(),
                ))
            })?
            .to_bytes()
            .to_vec();

        if !(200..300).contains(&status) {
            let msg = error_message_from_body(&body)
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

        let mut config: ServeConfig = serde_json::from_slice(&body)?;
        config.e_tag = etag;
        Ok(config)
    }

    /// Set the serve config.
    ///
    /// The `e_tag` field on the config is sent as the `If-Match` header
    /// for conditional updates.
    pub async fn set_serve_config(&self, config: &ServeConfig) -> Result<(), Error> {
        let body = serde_json::to_vec(config)?;
        let mut req = self.build_request("POST", "/localapi/v0/serve-config", Some(&body))?;
        if !config.e_tag.is_empty() {
            req.headers_mut().insert("If-Match", config.e_tag.parse().map_err(|e: hyper::header::InvalidHeaderValue| Error::Other(e.to_string()))?);
        }
        self.do_request_nice_req(req).await?;
        Ok(())
    }
}
