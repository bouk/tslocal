use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Start the IPN state machine with the given options.
    pub async fn start(&self, opts: &serde_json::Value) -> Result<(), Error> {
        let body = serde_json::to_vec(opts)?;
        self.post200("/localapi/v0/start", Some(&body)).await?;
        Ok(())
    }

    /// Start an interactive login flow.
    pub async fn start_login_interactive(&self) -> Result<(), Error> {
        self.post200("/localapi/v0/login-interactive", None).await?;
        Ok(())
    }

    /// Log out the current node.
    pub async fn logout(&self) -> Result<(), Error> {
        self.post200("/localapi/v0/logout", None).await?;
        Ok(())
    }
}
