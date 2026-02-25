use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get daemon metrics in Prometheus text exposition format.
    pub async fn daemon_metrics(&self) -> Result<Vec<u8>, Error> {
        self.get200("/localapi/v0/metrics").await
    }

    /// Get user metrics in Prometheus text exposition format.
    pub async fn user_metrics(&self) -> Result<Vec<u8>, Error> {
        self.get200("/localapi/v0/usermetrics").await
    }

    /// Increment a counter metric.
    pub async fn increment_counter(&self, name: &str, delta: i64) -> Result<(), Error> {
        let body = serde_json::to_vec(&[serde_json::json!({
            "Name": name,
            "Type": "counter",
            "Value": delta,
            "Op": "add",
        })])?;
        self.post200("/localapi/v0/upload-client-metrics", Some(&body))
            .await?;
        Ok(())
    }

    /// Increment a gauge metric.
    pub async fn increment_gauge(&self, name: &str, delta: i64) -> Result<(), Error> {
        let body = serde_json::to_vec(&[serde_json::json!({
            "Name": name,
            "Type": "gauge",
            "Value": delta,
            "Op": "add",
        })])?;
        self.post200("/localapi/v0/upload-client-metrics", Some(&body))
            .await?;
        Ok(())
    }

    /// Set a gauge metric to a specific value.
    pub async fn set_gauge(&self, name: &str, value: i64) -> Result<(), Error> {
        let body = serde_json::to_vec(&[serde_json::json!({
            "Name": name,
            "Type": "gauge",
            "Value": value,
            "Op": "set",
        })])?;
        self.post200("/localapi/v0/upload-client-metrics", Some(&body))
            .await?;
        Ok(())
    }
}
