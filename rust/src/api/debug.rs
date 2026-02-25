use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Invoke a debug action (e.g., "rebind", "restun").
    pub async fn debug_action(&self, action: &str) -> Result<(), Error> {
        self.post200(
            &format!(
                "/localapi/v0/debug?action={}",
                crate::urlencode(action)
            ),
            None,
        )
        .await?;
        Ok(())
    }

    /// Invoke a debug action with a body.
    pub async fn debug_action_body(&self, action: &str, body: &[u8]) -> Result<(), Error> {
        self.post200(
            &format!(
                "/localapi/v0/debug?action={}",
                crate::urlencode(action)
            ),
            Some(body),
        )
        .await?;
        Ok(())
    }

    /// Invoke a debug action and return the JSON result.
    pub async fn debug_result_json(&self, action: &str) -> Result<serde_json::Value, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/debug?action={}",
                    crate::urlencode(action)
                ),
                None,
            )
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get packet filter rules.
    pub async fn debug_packet_filter_rules(&self) -> Result<serde_json::Value, Error> {
        let body = self
            .post200("/localapi/v0/debug-packet-filter-rules", None)
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Set node key expiry to a time in the future (in seconds from now).
    pub async fn debug_set_expire_in(&self, secs: i64) -> Result<(), Error> {
        let expiry = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64
            + secs;
        self.post200(
            &format!("/localapi/v0/set-expiry-sooner?expiry={}", expiry),
            None,
        )
        .await?;
        Ok(())
    }

    /// Get the event bus graph.
    pub async fn event_bus_graph(&self) -> Result<Vec<u8>, Error> {
        self.get200("/localapi/v0/debug-bus-graph").await
    }
}
