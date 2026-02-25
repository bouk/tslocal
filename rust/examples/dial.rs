use http_body_util::BodyExt;
use hyper::rt::{Read, Write};
use hyper_util::client::legacy::connect::{Connected, Connection};
use hyper_util::client::legacy::Client as HyperClient;
use hyper_util::rt::TokioExecutor;
use std::error::Error;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::task::{Context, Poll};
use tslocalapi::Client;

/// A stream returned by the Tailscale connector, wrapping a hyper Upgraded connection.
struct TailscaleStream(hyper::upgrade::Upgraded);

impl Read for TailscaleStream {
    fn poll_read(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        buf: hyper::rt::ReadBufCursor<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        Pin::new(&mut self.0).poll_read(cx, buf)
    }
}

impl Write for TailscaleStream {
    fn poll_write(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
        buf: &[u8],
    ) -> Poll<Result<usize, std::io::Error>> {
        Pin::new(&mut self.0).poll_write(cx, buf)
    }
    fn poll_flush(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        Pin::new(&mut self.0).poll_flush(cx)
    }
    fn poll_shutdown(
        mut self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Result<(), std::io::Error>> {
        Pin::new(&mut self.0).poll_shutdown(cx)
    }
}

impl Connection for TailscaleStream {
    fn connected(&self) -> Connected {
        Connected::new()
    }
}

/// A hyper connector that dials through Tailscale.
#[derive(Clone)]
struct TailscaleConnector {
    client: Arc<Client>,
}

impl tower_service::Service<hyper::Uri> for TailscaleConnector {
    type Response = TailscaleStream;
    type Error = tslocalapi::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, _cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Poll::Ready(Ok(()))
    }

    fn call(&mut self, uri: hyper::Uri) -> Self::Future {
        let client = self.client.clone();
        Box::pin(async move {
            let host = uri.host().expect("uri must have a host").to_string();
            let port = uri.port_u16().unwrap_or(80);
            let conn = client.dial_tcp(&host, port).await?;
            Ok(TailscaleStream(conn.into_inner()))
        })
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let url: hyper::Uri = std::env::args()
        .nth(1)
        .expect("usage: dial <url>")
        .parse()?;

    let connector = TailscaleConnector {
        client: Arc::new(Client::new()),
    };

    let hyper_client =
        HyperClient::builder(TokioExecutor::new()).build::<_, http_body_util::Empty<bytes::Bytes>>(connector);

    let resp = hyper_client.get(url).await?;
    let status = resp.status();

    let body = resp.into_body().collect().await?.to_bytes();

    println!("HTTP {}", status);
    println!("{}", String::from_utf8_lossy(&body));
    Ok(())
}
