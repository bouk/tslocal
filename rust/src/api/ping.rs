use crate::client::Client;
use crate::error::Error;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct PingResult {
    #[serde(rename = "IP")]
    #[serde(default)]
    pub ip: String,
    #[serde(rename = "NodeIP")]
    #[serde(default)]
    pub node_ip: String,
    #[serde(default)]
    pub node_name: String,
    #[serde(default)]
    pub err: String,
    #[serde(default)]
    pub latency_seconds: f64,
    #[serde(default)]
    pub endpoint: String,
    #[serde(rename = "DERPRegionID")]
    #[serde(default)]
    pub derp_region_id: i32,
    #[serde(rename = "DERPRegionCode")]
    #[serde(default)]
    pub derp_region_code: String,
    #[serde(rename = "PeerAPIPort")]
    #[serde(default)]
    pub peer_api_port: u16,
    #[serde(rename = "IsLocalIP")]
    #[serde(default)]
    pub is_local_ip: bool,
}

impl Client {
    /// Ping a peer by IP address.
    pub async fn ping(
        &self,
        ip: &str,
        ping_type: &str,
    ) -> Result<PingResult, Error> {
        self.ping_with_opts(ip, ping_type, 0).await
    }

    /// Ping a peer with options.
    pub async fn ping_with_opts(
        &self,
        ip: &str,
        ping_type: &str,
        size: u32,
    ) -> Result<PingResult, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/ping?ip={}&type={}&size={}",
                    crate::urlencode(ip),
                    crate::urlencode(ping_type),
                    size
                ),
                None,
            )
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
