use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Check if IP forwarding is properly configured.
    pub async fn check_ip_forwarding(&self) -> Result<Option<String>, Error> {
        let body = self.get200("/localapi/v0/check-ip-forwarding").await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        Ok(res.get("Warning").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).map(|s| s.to_string()))
    }

    /// Check if UDP GRO forwarding is properly configured.
    pub async fn check_udp_gro_forwarding(&self) -> Result<Option<String>, Error> {
        let body = self
            .get200("/localapi/v0/check-udp-gro-forwarding")
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        Ok(res.get("Warning").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).map(|s| s.to_string()))
    }

    /// Check reverse path filtering.
    pub async fn check_reverse_path_filtering(&self) -> Result<Option<String>, Error> {
        let body = self
            .get200("/localapi/v0/check-reverse-path-filtering")
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        Ok(res.get("Warning").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).map(|s| s.to_string()))
    }

    /// Enable UDP GRO forwarding.
    pub async fn set_udp_gro_forwarding(&self) -> Result<Option<String>, Error> {
        let body = self
            .get200("/localapi/v0/set-udp-gro-forwarding")
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        Ok(res.get("Warning").and_then(|v| v.as_str()).filter(|s| !s.is_empty()).map(|s| s.to_string()))
    }

    /// Check prefs without making changes.
    pub async fn check_prefs(&self, prefs: &crate::types::Prefs) -> Result<(), Error> {
        let body = serde_json::to_vec(prefs)?;
        self.post200("/localapi/v0/check-prefs", Some(&body))
            .await?;
        Ok(())
    }

    /// Get goroutine dump.
    pub async fn goroutines(&self) -> Result<Vec<u8>, Error> {
        self.get200("/localapi/v0/goroutines").await
    }

    /// Get pprof profile data.
    pub async fn pprof(&self, pprof_type: &str, secs: u32) -> Result<Vec<u8>, Error> {
        self.get200(&format!(
            "/localapi/v0/pprof?name={}&seconds={}",
            crate::urlencode(pprof_type),
            secs
        ))
        .await
    }

    /// File a bug report. Returns the log marker.
    pub async fn bug_report(&self, note: &str) -> Result<String, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/bugreport?note={}",
                    crate::urlencode(note)
                ),
                None,
            )
            .await?;
        Ok(String::from_utf8_lossy(&body).trim().to_string())
    }

    /// File a bug report with options. Returns the log marker.
    ///
    /// If `diagnose` is true, include diagnostic information in the report.
    pub async fn bug_report_with_opts(
        &self,
        note: &str,
        diagnose: bool,
    ) -> Result<String, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/bugreport?note={}&diagnose={}",
                    crate::urlencode(note),
                    diagnose
                ),
                None,
            )
            .await?;
        Ok(String::from_utf8_lossy(&body).trim().to_string())
    }

    /// Shut down the tailscaled daemon.
    pub async fn shutdown_tailscaled(&self) -> Result<(), Error> {
        self.post200("/localapi/v0/shutdown", None).await?;
        Ok(())
    }

    /// Reload daemon config.
    pub async fn reload_config(&self) -> Result<bool, Error> {
        let body = self
            .post200("/localapi/v0/reload-config", None)
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        if let Some(err) = res.get("Err").and_then(|v| v.as_str()).filter(|s| !s.is_empty()) {
            return Err(Error::Other(err.to_string()));
        }
        Ok(res.get("Reloaded").and_then(|v| v.as_bool()).unwrap_or(false))
    }

    /// Check if SO_MARK is in use (Linux only).
    pub async fn check_so_mark_in_use(&self) -> Result<bool, Error> {
        let body = self
            .get200("/localapi/v0/check-so-mark-in-use")
            .await?;
        let res: serde_json::Value = serde_json::from_slice(&body)?;
        Ok(res.get("useSoMark").and_then(|v| v.as_bool()).unwrap_or(false))
    }

    /// Get the app connector route info.
    pub async fn get_app_connector_route_info(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/appc-route-info").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Query a feature (e.g. "serve", "funnel").
    pub async fn query_feature(&self, feature: &str) -> Result<serde_json::Value, Error> {
        let body = self
            .post200(
                &format!(
                    "/localapi/v0/query-feature?feature={}",
                    crate::urlencode(feature)
                ),
                None,
            )
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Check for available updates.
    pub async fn check_update(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/update/check").await?;
        Ok(serde_json::from_slice(&body)?)
    }

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

    /// Disconnect from the control server.
    pub async fn disconnect_control(&self) -> Result<(), Error> {
        self.post200("/localapi/v0/disconnect-control", None)
            .await?;
        Ok(())
    }

    /// Get the DNS OS config.
    pub async fn get_dns_os_config(&self) -> Result<serde_json::Value, Error> {
        let body = self.get200("/localapi/v0/dns-osconfig").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Query optional features supported by the daemon.
    pub async fn query_optional_features(&self) -> Result<serde_json::Value, Error> {
        let body = self
            .post200("/localapi/v0/debug-optional-features", None)
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }
}
