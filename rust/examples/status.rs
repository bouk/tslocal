use tslocal::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    let status = client.status().await?;
    println!("{}", serde_json::to_string_pretty(&status)?);
    Ok(())
}
