# tslocal

Client libraries for the [Tailscale Local API](https://tailscale.com/kb/1242/tailscale-api-local) in Rust, Python, and TypeScript.

These are direct ports of the official Go client (`tailscale/client/local`), targeting Tailscale **v1.94.1**.

## Libraries

| Language | Path | Runtime |
|----------|------|---------|
| Rust | [`rust/`](rust/) | async/tokio |
| Python | [`python/`](python/) | sync |
| TypeScript | [`ts/`](ts/) | Node.js |

## Installation

**Rust** — add to `Cargo.toml`:
```toml
[dependencies]
tslocal = "0.1.0"
```

**Python**:
```sh
pip install tslocal
```

**TypeScript**:
```sh
npm install tslocal
```

## Usage

All three libraries communicate with the local Tailscale daemon over a Unix domain socket. The daemon must be running on the same machine.

### Rust

```rust
use tslocal::LocalClient;

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
from tslocal import LocalClient

with LocalClient() as client:
    status = client.status()
    print(f"Tailscale version: {status.version}")
```

### TypeScript

```typescript
import { LocalClient } from "tslocal";

const client = new LocalClient();
const status = await client.status();
console.log(`Tailscale version: ${status.Version}`);
client.destroy();
```

## Supported Methods

| Description | Go | Rust | Python | TypeScript |
|---|---|---|---|---|
| Get full node status including peers | `Status` | `status` | `status` | `status` |
| Get node status without peer information | `StatusWithoutPeers` | `status_without_peers` | `status_without_peers` | `statusWithoutPeers` |
| Look up identity by IP address | `WhoIs` | `who_is` | `who_is` | `whoIs` |
| Look up identity by node key | `WhoIsNodeKey` | `who_is_node_key` | `who_is_node_key` | `whoIsNodeKey` |
| Look up identity with proto and address | `WhoIsProto` | `who_is_proto` | `who_is_proto` | `whoIsProto` |
| Get TLS certificate and private key | `CertPair` | `cert_pair` | `cert_pair` | `certPair` |
| Get TLS certificate with minimum validity | `CertPairWithValidity` | `cert_pair_with_validity` | `cert_pair_with_validity` | `certPairWithValidity` |
| Get current serve configuration | `GetServeConfig` | `get_serve_config` | `get_serve_config` | `getServeConfig` |
| Set serve configuration | `SetServeConfig` | `set_serve_config` | `set_serve_config` | `setServeConfig` |

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
