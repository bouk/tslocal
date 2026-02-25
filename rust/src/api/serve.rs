use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get the current serve config. Returns the JSON body bytes.
    pub async fn get_serve_config(&self) -> Result<Vec<u8>, Error> {
        self.get200("/localapi/v0/serve-config").await
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
