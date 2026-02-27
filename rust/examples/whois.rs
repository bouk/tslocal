use tslocal::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = std::env::args().nth(1).expect("usage: whois <addr>");
    let client = Client::new();
    let result = client.who_is(&addr).await?;
    println!("{}", serde_json::to_string_pretty(&result)?);
    Ok(())
}
