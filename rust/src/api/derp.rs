use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get the current DERP map.
    pub async fn current_derp_map(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/derpmap").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Debug a DERP region by ID or code.
    pub async fn debug_derp_region(
        &self,
        region_id_or_code: &str,
    ) -> Result<serde_json::Value, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/debug-derp-region?region={}",
                    crate::urlencode(region_id_or_code)
                ),
                None,
            )
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get debug info about peer relay sessions.
    pub async fn debug_peer_relay_sessions(&self) -> Result<serde_json::Value, Error> {
        let body = self
            .get200("/localapi/v0/debug-peer-relay-sessions")
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
