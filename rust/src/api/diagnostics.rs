use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get an OIDC ID token for an audience.
    pub async fn id_token(&self, aud: &str) -> Result<serde_json::Value, Error> {
        let body = self
            .get200(&format!(
                "/localapi/v0/id-token?aud={}",
                crate::urlencode(aud)
            ))
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
