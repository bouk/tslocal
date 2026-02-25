use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Query DNS.
    pub async fn query_dns(
        &self,
        name: &str,
        query_type: &str,
    ) -> Result<serde_json::Value, Error> {
        let body = self
            .get200(&format!(
                "/localapi/v0/dns-query?name={}&type={}",
                crate::urlencode(name),
                crate::urlencode(query_type)
            ))
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
