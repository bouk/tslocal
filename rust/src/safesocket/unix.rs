#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use tokio::net::{UnixListener, UnixStream};

    #[tokio::test]
    async fn test_unix_socket_connect() {
        let dir = tempfile::tempdir().unwrap();
        let sock_path = dir.path().join("test.sock");
        let sock_path_str = sock_path.to_str().unwrap().to_string();

        let listener = UnixListener::bind(&sock_path).unwrap();

        let connect_handle = tokio::spawn(async move {
            UnixStream::connect(&sock_path_str).await
        });

        let (server_conn, _) = listener.accept().await.unwrap();
        let client_conn = connect_handle.await.unwrap().unwrap();

        // Both sides should be connected
        drop(server_conn);
        drop(client_conn);
    }
}
