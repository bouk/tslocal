use tslocalapi::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let config = client.get_serve_config().await?;
    eprintln!("ETag: {}", config.e_tag);
    println!("{}", serde_json::to_string_pretty(&config)?);
    Ok(())
}
