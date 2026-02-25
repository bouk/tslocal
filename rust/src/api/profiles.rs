use crate::client::Client;
use crate::error::Error;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct ProfileStatus {
    #[serde(default)]
    pub current_profile: crate::types::LoginProfile,
    #[serde(default)]
    pub all_profiles: Vec<crate::types::LoginProfile>,
}

impl Client {
    /// Get profile status (current profile and all profiles).
    pub async fn profile_status(&self) -> Result<ProfileStatus, Error> {
        let body = self.get200("/localapi/v0/profiles/current").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Switch to the profile with the given ID.
    pub async fn switch_profile(&self, profile_id: &str) -> Result<(), Error> {
        self.post200(
            &format!("/localapi/v0/profiles/{}", profile_id),
            None,
        )
        .await?;
        Ok(())
    }

    /// Switch to an empty (new) profile.
    pub async fn switch_to_empty_profile(&self) -> Result<(), Error> {
        self.post200("/localapi/v0/profiles/", None).await?;
        Ok(())
    }

    /// Delete the profile with the given ID.
    pub async fn delete_profile(&self, profile_id: &str) -> Result<(), Error> {
        self.do_request_nice(
            "DELETE",
            &format!("/localapi/v0/profiles/{}", profile_id),
            None,
        )
        .await?;
        Ok(())
    }
}
