import { Client, jsonReplacer } from "../src/index.js";

const client = new Client();
const status = await client.status();
console.log(JSON.stringify(status, jsonReplacer, 2));
client.destroy();
