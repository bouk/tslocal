use tslocalapi::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let (body, etag) = client.get_serve_config().await?;
    let config: serde_json::Value = serde_json::from_slice(&body)?;
    eprintln!("ETag: {etag}");
    println!("{}", serde_json::to_string_pretty(&config)?);
    Ok(())
}
