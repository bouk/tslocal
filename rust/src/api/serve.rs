use crate::client::Client;
use crate::error::{error_message_from_body, Error};
use http_body_util::BodyExt;

impl Client {
    /// Get the current serve config. Returns the JSON body bytes and the ETag header.
    pub async fn get_serve_config(&self) -> Result<(Vec<u8>, String), Error> {
        let req = self.build_request_with_headers("GET", "/localapi/v0/serve-config", None, &[])?;
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

        Ok((body, etag))
    }

    /// Set the serve config. Optionally pass an etag for conditional update.
    pub async fn set_serve_config(&self, config: &[u8], etag: Option<&str>) -> Result<(), Error> {
        let path = "/localapi/v0/serve-config";
        let headers: Vec<(&str, &str)> = etag
            .map(|e| vec![("If-Match", e)])
            .unwrap_or_default();
        self.do_request_nice_with_headers("POST", path, Some(config), &headers)
            .await?;
        Ok(())
    }
}
