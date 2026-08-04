import { readFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";

const frontendRoot = new URL("../", import.meta.url);
const schemaPath = new URL("../src/api/generated/schema.ts", import.meta.url);
const before = await readFile(schemaPath, "utf8").catch(() => null);
const command = process.platform === "win32" ? (process.env.ComSpec ?? "cmd.exe") : "npm";
const args = process.platform === "win32"
  ? ["/d", "/s", "/c", "npm run api:generate"]
  : ["run", "api:generate"];
const generated = spawnSync(command, args, {
  cwd: frontendRoot,
  encoding: "utf8",
  stdio: "inherit",
});

if (generated.error) {
  console.error(`无法生成 OpenAPI 类型：${generated.error.message}`);
  process.exit(1);
}
if (generated.status !== 0) {
  process.exit(generated.status ?? 1);
}

const after = await readFile(schemaPath, "utf8");
if (before !== after) {
  console.error("OpenAPI 类型漂移：src/api/generated/schema.ts 已重新生成，请核对并保留更新。");
  process.exit(1);
}
console.log("OpenAPI 类型无漂移。");
