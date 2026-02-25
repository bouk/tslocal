use crate::error::{error_message_from_body, Error};
use crate::safesocket;
use crate::transport::TransportConfig;
use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::{Request, Response};
use hyper_util::client::legacy::Client as HyperClient;
use hyper_util::rt::TokioExecutor;

/// Client for the Tailscale Local API.
///
/// Connections are pooled and reused via hyper's connection management.
pub struct Client {
    config: TransportConfig,
    unix_client: Option<HyperClient<hyperlocal::UnixConnector, Full<Bytes>>>,
    tcp_client: Option<HyperClient<hyper_util::client::legacy::connect::HttpConnector, Full<Bytes>>>,
}

impl Client {
    /// Create a new client with auto-detected transport settings.
    pub fn new() -> Self {
        Self::with_config(TransportConfig::detect())
    }

    /// Create a new client with explicit transport configuration.
    pub fn with_config(config: TransportConfig) -> Self {
        let mut client = Self {
            unix_client: None,
            tcp_client: None,
            config,
        };

        if client.config.uses_tcp() {
            client.tcp_client = Some(
                HyperClient::builder(TokioExecutor::new())
                    .pool_idle_timeout(std::time::Duration::from_secs(60))
                    .build_http(),
            );
        } else {
            client.unix_client = Some(
                HyperClient::builder(TokioExecutor::new())
                    .pool_idle_timeout(std::time::Duration::from_secs(60))
                    .build(hyperlocal::UnixConnector),
            );
        }

        client
    }

    /// Send an HTTP request to the local API and return the response.
    pub(crate) async fn send_request(
        &self,
        req: Request<Full<Bytes>>,
    ) -> Result<Response<Incoming>, Error> {
        let result = if self.config.uses_tcp() {
            self.tcp_client
                .as_ref()
                .expect("tcp_client not initialized")
                .request(req)
                .await
        } else {
            self.unix_client
                .as_ref()
                .expect("unix_client not initialized")
                .request(req)
                .await
        };

        result.map_err(|e| Error::Connection {
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
        let uri: hyper::Uri = if self.config.uses_tcp() {
            format!("{}{}", self.config.base_url(), path).parse().map_err(|e: hyper::http::uri::InvalidUri| Error::Other(e.to_string()))?
        } else {
            hyperlocal::Uri::new(&self.config.socket_path, path).into()
        };

        let body_bytes = body.map(Bytes::copy_from_slice).unwrap_or_default();

        let mut builder = Request::builder()
            .method(method)
            .uri(uri)
            .header("Host", safesocket::LOCAL_API_HOST)
            .header("Tailscale-Cap", safesocket::CURRENT_CAP_VERSION.to_string());

        if let Some(auth) = self.config.auth_header() {
            builder = builder.header("Authorization", auth);
        }

        for (key, value) in extra_headers {
            builder = builder.header(*key, *value);
        }

        builder
            .body(Full::new(body_bytes))
            .map_err(|e| Error::Other(e.to_string()))
    }

    /// Send a request and return status + body.
    pub async fn do_request(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<(u16, Vec<u8>), Error> {
        self.do_request_with_headers(method, path, body, &[]).await
    }

    /// Send a request with extra headers and return status + body.
    pub async fn do_request_with_headers(
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
    pub async fn do_request_nice(
        &self,
        method: &str,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<Vec<u8>, Error> {
        self.do_request_nice_with_headers(method, path, body, &[]).await
    }

    /// Send a request with extra headers and map non-2xx status codes to errors.
    pub async fn do_request_nice_with_headers(
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
    pub async fn get200(&self, path: &str) -> Result<Vec<u8>, Error> {
        self.do_request_nice("GET", path, None).await
    }

    /// POST request expecting 2xx response.
    pub async fn post200(
        &self,
        path: &str,
        body: Option<&[u8]>,
    ) -> Result<Vec<u8>, Error> {
        self.do_request_nice("POST", path, body).await
    }
}

impl Default for Client {
    fn default() -> Self {
        Self::new()
    }
}
