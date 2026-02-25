use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Set component debug logging for a duration (in seconds).
    pub async fn set_component_debug_logging(
        &self,
        component: &str,
        secs: i64,
    ) -> Result<(), Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/component-debug-logging?component={}&secs={}",
                    crate::urlencode(component),
                    secs
                ),
                None,
            )
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        if let Some(err) = res.get("Error").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            return Err(Error::Other(err.to_string()));
        }
        Ok(())
    }

    /// Set a dev store key-value pair.
    pub async fn set_dev_store_key_value(
        &self,
        key: &str,
        value: &str,
    ) -> Result<(), Error> {
        self.post200(
            &format!(
                "/localapi/v0/dev-set-state-store?key={}&value={}",
                crate::urlencode(key),
                crate::urlencode(value)
            ),
            None,
        )
        .await?;
        Ok(())
    }
}
