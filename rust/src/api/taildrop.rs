use crate::client::Client;
use crate::error::Error;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct WaitingFile {
    pub name: String,
    pub size: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "PascalCase")]
pub struct FileTarget {
    pub node: serde_json::Value,
    #[serde(rename = "PeerAPIURL")]
    pub peer_api_url: String,
}

impl Client {
    /// Get the list of waiting Taildrop files.
    pub async fn waiting_files(&self) -> Result<Vec<WaitingFile>, Error> {
        let body = self.get200("/localapi/v0/files/?waitsec=0").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get the list of waiting Taildrop files, waiting up to `wait_secs` seconds.
    pub async fn await_waiting_files(&self, wait_secs: u64) -> Result<Vec<WaitingFile>, Error> {
        let body = self
            .get200(&format!("/localapi/v0/files/?waitsec={}", wait_secs))
            .await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Delete a waiting Taildrop file.
    pub async fn delete_waiting_file(&self, base_name: &str) -> Result<(), Error> {
        self.do_request_nice(
            "DELETE",
            &format!("/localapi/v0/files/{}", crate::urlencode(base_name)),
            None,
        )
        .await?;
        Ok(())
    }

    /// Get the list of file targets (nodes that can receive files).
    pub async fn file_targets(&self) -> Result<Vec<FileTarget>, Error> {
        let body = self.get200("/localapi/v0/file-targets").await?;
        Ok(serde_json::from_slice(&body)?)
    }

    /// Get the contents of a waiting Taildrop file.
    /// Returns (file_bytes, content_length).
    pub async fn get_waiting_file(&self, base_name: &str) -> Result<(Vec<u8>, i64), Error> {
        let body = self
            .get200(&format!(
                "/localapi/v0/files/{}",
                crate::urlencode(base_name)
            ))
            .await?;
        let len = body.len() as i64;
        Ok((body, len))
    }

    /// Push a file to a target node.
    pub async fn push_file(
        &self,
        target: &str,
        name: &str,
        data: &[u8],
    ) -> Result<(), Error> {
        self.do_request_nice(
            "PUT",
            &format!(
                "/localapi/v0/file-put/{}/{}",
                crate::urlencode(target),
                crate::urlencode(name)
            ),
            Some(data),
        )
        .await?;
        Ok(())
    }
}
