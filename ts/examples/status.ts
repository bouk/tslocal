import { LocalClient } from "../src/index.js";

const client = new LocalClient();
const status = await client.status();
console.log(JSON.stringify(status, null, 2));
client.destroy();
