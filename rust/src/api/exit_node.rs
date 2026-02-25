use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Toggle the use of an exit node on or off.
    pub async fn set_use_exit_node(&self, on: bool) -> Result<(), Error> {
        self.post200(
            &format!(
                "/localapi/v0/set-use-exit-node-enabled?enabled={}",
                on
            ),
            None,
        )
        .await?;
        Ok(())
    }

    /// Get an exit node suggestion.
    pub async fn suggest_exit_node(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/suggest-exit-node").await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
