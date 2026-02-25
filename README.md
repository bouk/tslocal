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

## API Coverage

The libraries cover the full Tailscale Local API surface, including:

- **Status** — node status, peer information
- **WhoIs** — identity lookup by IP address or node key
- **Auth** — login, logout, interactive login
- **Prefs** — get/edit/check preferences
- **Profiles** — list, switch, create, delete profiles
- **DNS** — query DNS, set DNS records, OS DNS config
- **Ping** — ping peers via DERP, TSMP, or ICMPv4
- **DERP** — DERP map, region debugging, relay sessions
- **Certificates** — TLS cert pairs, SNI expansion
- **Serve** — get/set serve config
- **Exit Nodes** — enable/disable, suggestions
- **Taildrop** — send/receive files
- **Taildrive** — share management
- **Network Lock** — tailnet lock operations
- **Metrics** — daemon/user metrics, counters, gauges
- **Diagnostics** — bug reports, goroutines, pprof, config reload

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
