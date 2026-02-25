use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get the list of Taildrive shares.
    pub async fn drive_share_list(&self) -> Result<Vec<serde_json::Value>, Error> {
        let body = self.get200("/localapi/v0/drive/shares").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Add or update a Taildrive share.
    pub async fn drive_share_set(&self, share: &serde_json::Value) -> Result<(), Error> {
        let body = serde_json::to_vec(share)?;
        self.do_request_nice("PUT", "/localapi/v0/drive/shares", Some(&body))
            .await?;
        Ok(())
    }

    /// Remove a Taildrive share by name.
    pub async fn drive_share_remove(&self, name: &str) -> Result<(), Error> {
        self.do_request_nice("DELETE", "/localapi/v0/drive/shares", Some(name.as_bytes()))
            .await?;
        Ok(())
    }

    /// Rename a Taildrive share.
    pub async fn drive_share_rename(&self, old_name: &str, new_name: &str) -> Result<(), Error> {
        let body = serde_json::to_vec(&[old_name, new_name])?;
        self.post200("/localapi/v0/drive/shares", Some(&body))
            .await?;
        Ok(())
    }

    /// Set the Taildrive file server address.
    pub async fn drive_set_server_addr(&self, addr: &str) -> Result<(), Error> {
        self.do_request_nice(
            "PUT",
            "/localapi/v0/drive/fileserver-address",
            Some(addr.as_bytes()),
        )
        .await?;
        Ok(())
    }
}
