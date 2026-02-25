use crate::client::Client;
use crate::error::Error;
use crate::types::Status;

impl Client {
    /// Get the current tailscaled status.
    pub async fn status(&self) -> Result<Status, Error> {
        let body = self.get200("/localapi/v0/status").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get the current tailscaled status without peer information.
    pub async fn status_without_peers(&self) -> Result<Status, Error> {
        let body = self
            .get200("/localapi/v0/status?peers=false")
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
