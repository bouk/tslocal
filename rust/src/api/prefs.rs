use crate::client::Client;
use crate::error::Error;
use crate::types::{MaskedPrefs, Prefs};

impl Client {
    /// Get current prefs.
    pub async fn get_prefs(&self) -> Result<Prefs, Error> {
        let body = self.get200("/localapi/v0/prefs").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Edit prefs with a MaskedPrefs patch.
    pub async fn edit_prefs(&self, prefs: &MaskedPrefs) -> Result<Prefs, Error> {
        let body = serde_json::to_vec(prefs)?;
        let resp = self
            .do_request_nice("PATCH", "/localapi/v0/prefs", Some(&body))
            .await?;
        Ok(serde_json::from_slice(&resp)?)
    }
}
