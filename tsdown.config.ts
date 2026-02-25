import { defineConfig } from "tsdown";

export default defineConfig({
  entry: ["ts/src/index.ts"],
  format: ["esm", "cjs"],
  dts: true,
  sourcemap: true,
  outDir: "dist",
});
