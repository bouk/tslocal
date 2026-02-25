use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get the network lock (TKA) status.
    pub async fn network_lock_status(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/tka/status").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Initialize network lock.
    pub async fn network_lock_init(
        &self,
        keys: &serde_json::Value,
        disablement_values: &[Vec<u8>],
        support_disablement: &[u8],
    ) -> Result<serde_json::Value, Error> {
        let body = serde_json::to_vec(&serde_json::json!({
            "Keys": keys,
            "DisablementValues": disablement_values,
            "SupportDisablement": support_disablement,
        }))?;
        let resp = self
            .post200("/localapi/v0/tka/init", Some(&body))
            .await?;
        Ok(serde_json::from_slice(&resp)?)
    }

    /// Wrap a pre-auth key for use with network lock.
    pub async fn network_lock_wrap_preauth_key(
        &self,
        ts_key: &str,
        tka_key: &str,
    ) -> Result<String, Error> {
        let body = serde_json::to_vec(&serde_json::json!({
            "TSKey": ts_key,
            "TKAKey": tka_key,
        }))?;
        let resp = self
            .post200("/localapi/v0/tka/wrap-preauth-key", Some(&body))
            .await?;
        Ok(String::from_utf8_lossy(&resp).to_string())
    }

    /// Modify network lock keys.
    pub async fn network_lock_modify(
        &self,
        add_keys: &serde_json::Value,
        remove_keys: &serde_json::Value,
    ) -> Result<(), Error> {
        let body = serde_json::to_vec(&serde_json::json!({
            "AddKeys": add_keys,
            "RemoveKeys": remove_keys,
        }))?;
        self.post200("/localapi/v0/tka/modify", Some(&body))
            .await?;
        Ok(())
    }

    /// Sign a node key for network lock.
    pub async fn network_lock_sign(
        &self,
        node_key: &str,
        rotation_public: &[u8],
    ) -> Result<(), Error> {
        let body = serde_json::to_vec(&serde_json::json!({
            "NodeKey": node_key,
            "RotationPublic": rotation_public,
        }))?;
        self.post200("/localapi/v0/tka/sign", Some(&body))
            .await?;
        Ok(())
    }

    /// Get signatures affected by a key ID.
    pub async fn network_lock_affected_sigs(
        &self,
        key_id: &[u8],
    ) -> Result<serde_json::Value, Error> {
        let resp = self
            .post200("/localapi/v0/tka/affected-sigs", Some(key_id))
            .await?;
        Ok(serde_json::from_slice(&resp)?)
    }

    /// Get network lock log entries.
    pub async fn network_lock_log(
        &self,
        max_entries: u32,
    ) -> Result<serde_json::Value, Error> {
        let body = self
            .get200(&format!(
                "/localapi/v0/tka/log?limit={}",
                max_entries
            ))
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Forcibly disable network lock on this node.
    pub async fn network_lock_force_local_disable(&self) -> Result<(), Error> {
        let body = serde_json::to_vec(&serde_json::json!({}))?;
        self.post200("/localapi/v0/tka/force-local-disable", Some(&body))
            .await?;
        Ok(())
    }

    /// Verify a network lock signing deeplink.
    pub async fn network_lock_verify_signing_deeplink(
        &self,
        url: &str,
    ) -> Result<serde_json::Value, Error> {
        let body = serde_json::to_vec(&serde_json::json!({ "URL": url }))?;
        let resp = self
            .post200("/localapi/v0/tka/verify-deeplink", Some(&body))
            .await?;
        Ok(serde_json::from_slice(&resp)?)
    }

    /// Generate a recovery AUM for network lock.
    pub async fn network_lock_gen_recovery_aum(
        &self,
        remove_keys: &serde_json::Value,
        fork_from: &str,
    ) -> Result<Vec<u8>, Error> {
        let body = serde_json::to_vec(&serde_json::json!({
            "Keys": remove_keys,
            "ForkFrom": fork_from,
        }))?;
        self.post200("/localapi/v0/tka/generate-recovery-aum", Some(&body))
            .await
    }

    /// Co-sign a recovery AUM.
    pub async fn network_lock_cosign_recovery_aum(
        &self,
        aum: &[u8],
    ) -> Result<Vec<u8>, Error> {
        self.post200("/localapi/v0/tka/cosign-recovery-aum", Some(aum))
            .await
    }

    /// Submit a recovery AUM to the control plane.
    pub async fn network_lock_submit_recovery_aum(
        &self,
        aum: &[u8],
    ) -> Result<(), Error> {
        self.post200("/localapi/v0/tka/submit-recovery-aum", Some(aum))
            .await?;
        Ok(())
    }

    /// Disable network lock across the tailnet.
    pub async fn network_lock_disable(&self, secret: &[u8]) -> Result<(), Error> {
        self.post200("/localapi/v0/tka/disable", Some(secret))
            .await?;
        Ok(())
    }
}
