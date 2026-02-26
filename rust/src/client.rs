use crate::error::{error_message_from_body, Error};
use crate::safesocket;
use crate::transport::{TailscaleConnector, TransportConfig, auth_header_for_token, resolve_port_and_token};
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
                auth_header_for_token(token).parse().unwrap(),
            );
            Request::from_parts(parts, body)
        } else {
            req
        };

        self.client.request(req).await.map_err(|e| Error::Connection {
            message: e.to_string(),
        })
    }

    /// Build an HTTP request with standard headers and optional extra headers.
    pub(crate) fn build_request_with_headers(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
        extra_headers: &[(&str, &str)],
    ) -> Result<Request<Full<Bytes>>, Error> {
        let uri: hyper::Uri = format!("http://{}{}", safesocket::LOCAL_API_HOST, path)
            .parse()
            .map_err(|e: hyper::http::uri::InvalidUri| Error::Other(e.to_string()))?;

        let body_bytes = body.map(Bytes::copy_from_slice).unwrap_or_default();

        let mut builder = Request::builder()
            .method(method)
            .uri(uri)
            .header("Host", safesocket::LOCAL_API_HOST)
            .header("Tailscale-Cap", safesocket::CURRENT_CAP_VERSION.to_string());

        for (key, value) in extra_headers {
            builder = builder.header(*key, *value);
        }

        builder
            .body(Full::new(body_bytes))
            .map_err(|e| Error::Other(e.to_string()))
    }

    /// Send a request and return status + body.
    pub(crate) async fn do_request(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<(u16, Vec<u8>), Error> {
        self.do_request_with_headers(method, path, body, &[]).await
    }

    /// Send a request with extra headers and return status + body.
    pub(crate) async fn do_request_with_headers(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
        extra_headers: &[(&str, &str)],
    ) -> Result<(u16, Vec<u8>), Error> {
        let req = self.build_request_with_headers(method, path, body, extra_headers)?;
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

    /// Send a request and map non-2xx status codes to errors (like `doLocalRequestNiceError`).
    pub(crate) async fn do_request_nice(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<Vec<u8>, Error> {
        self.do_request_nice_with_headers(method, path, body, &[]).await
    }

    /// Send a request with extra headers and map non-2xx status codes to errors.
    pub(crate) async fn do_request_nice_with_headers(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
        extra_headers: &[(&str, &str)],
    ) -> Result<Vec<u8>, Error> {
        let (status, body) = self.do_request_with_headers(method, path, body, extra_headers).await?;
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
