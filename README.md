# tslocalapi

Client libraries for the [Tailscale Local API](https://tailscale.com/kb/1242/tailscale-api-local) in Rust, Python, and TypeScript.

These are direct ports of the official Go client (`tailscale/client/local`), targeting Tailscale **v1.94.1**.

## Libraries

| Language | Path | Runtime |
|----------|------|---------|
| Rust | [`rust/`](rust/) | async/tokio |
| Python | [`python/`](python/) | async/asyncio |
| TypeScript | [`ts/`](ts/) | Node.js |

## Installation

**Rust** — add to `Cargo.toml`:
```toml
[dependencies]
tslocalapi = { git = "https://github.com/bouk/tslocalapi", subdirectory = "rust" }
```

**Python**:
```sh
pip install git+https://github.com/bouk/tslocalapi
```

**TypeScript**:
```sh
npm install github:bouk/tslocalapi
```

## Usage

All three libraries communicate with the local Tailscale daemon over a Unix domain socket. The daemon must be running on the same machine.

### Rust

```rust
use tslocalapi::LocalClient;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = LocalClient::new();
    let status = client.status().await?;
    println!("Tailscale version: {}", status.version);
    Ok(())
}
```

### Python

```python
from tslocalapi import LocalClient

async def main():
    async with LocalClient() as client:
        status = await client.status()
        print(f"Tailscale version: {status.version}")
```

### TypeScript

```typescript
import { LocalClient } from "tslocalapi";

const client = new LocalClient();
const status = await client.status();
console.log(`Tailscale version: ${status.Version}`);
client.destroy();
```

## Supported Methods

| Method | Description |
|--------|-------------|
| `status` | Get full node status including peers |
| `status_without_peers` | Get node status without peer information |
| `who_is` | Look up identity by IP address |
| `who_is_node_key` | Look up identity by node key |
| `who_is_proto` | Look up identity with custom WhoIsRequest |
| `cert_pair` | Get TLS certificate and private key |
| `cert_pair_with_validity` | Get TLS certificate with minimum validity |
| `get_serve_config` | Get current serve configuration |
| `set_serve_config` | Set serve configuration |
| `id_token` | Get an OIDC ID token for an audience |

## Build & Test

```sh
# Rust
cargo test
cargo check
cargo clippy

# Python
uv run pytest

# TypeScript
npm test
npx tsc --noEmit
```

## License

See [LICENSE](LICENSE).
