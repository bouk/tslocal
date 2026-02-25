use crate::client::Client;
use crate::error::Error;

impl Client {
    /// Get a TLS certificate and private key for the given domain.
    /// Returns (cert_pem, key_pem).
    pub async fn cert_pair(&self, domain: &str) -> Result<(Vec<u8>, Vec<u8>), Error> {
        self.cert_pair_with_validity(domain, 0).await
    }

    /// Get a TLS certificate with minimum validity duration (in seconds).
    /// Returns (cert_pem, key_pem).
    pub async fn cert_pair_with_validity(
        &self,
        domain: &str,
        min_validity_secs: u64,
    ) -> Result<(Vec<u8>, Vec<u8>), Error> {
        let path = format!(
            "/localapi/v0/cert/{}?type=pair&min_validity={}s",
            crate::urlencode(domain),
            min_validity_secs
        );
        let body = self.get200(&path).await?;

        // Response is key PEM then cert PEM, separated by "--\n--"
        let delimiter = b"--\n--";
        let pos = body
            .windows(delimiter.len())
            .position(|w| w == delimiter)
            .ok_or_else(|| Error::Other("unexpected cert response: no delimiter".into()))?;
        let split = pos + 3; // include "--\n"
        let key_pem = body[..split].to_vec();
        let cert_pem = body[split..].to_vec();
        Ok((cert_pem, key_pem))
    }
}
