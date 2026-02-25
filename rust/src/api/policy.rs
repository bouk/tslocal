use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get the effective policy for a given scope.
    pub async fn get_effective_policy(&self, scope: &str) -> Result<serde_json::Value, Error> {
        let body = self
            .get200(&format!(
                "/localapi/v0/policy/{}",
                crate::urlencode(scope)
            ))
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Reload the effective policy for a given scope.
    pub async fn reload_effective_policy(&self, scope: &str) -> Result<serde_json::Value, Error> {
        let body = self
            .post200(
                &format!("/localapi/v0/policy/{}", crate::urlencode(scope)),
                None,
            )
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
