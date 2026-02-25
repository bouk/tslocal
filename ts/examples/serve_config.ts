import { LocalClient, jsonReplacer } from "../src/index.js";

const client = new LocalClient();
const { config, etag } = await client.getServeConfig();
console.error(`ETag: ${etag}`);
console.log(JSON.stringify(config, jsonReplacer, 2));
client.destroy();
