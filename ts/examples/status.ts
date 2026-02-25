import { LocalClient, jsonReplacer } from "../src/index.js";

const client = new LocalClient();
const status = await client.status();
console.log(JSON.stringify(status, jsonReplacer, 2));
client.destroy();
