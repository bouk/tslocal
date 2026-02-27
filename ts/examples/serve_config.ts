import { Client } from "../src/index.js";
import { jsonReplacer } from "../src/json.js";

const client = new Client();
const config = await client.getServeConfig();
console.error(`ETag: ${config.ETag}`);
console.log(JSON.stringify(config, jsonReplacer, 2));
client.destroy();
