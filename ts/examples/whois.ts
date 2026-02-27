import { Client, jsonReplacer } from "../src/index.js";

const addr = process.argv[2];
if (!addr) {
  console.error("usage: whois <addr>");
  process.exit(1);
}

const client = new Client();
const result = await client.whoIs(addr);
console.log(JSON.stringify(result, jsonReplacer, 2));
client.destroy();
