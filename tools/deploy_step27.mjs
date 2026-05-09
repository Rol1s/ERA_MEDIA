import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { Client } = require("ssh2");

const host = process.env.ERA_SSH_HOST || "194.87.243.63";
const username = process.env.ERA_SSH_USER || "root";
const password = process.env.ERA_SSH_PASSWORD;
const archive = process.env.ERA_ARCHIVE || "era-media-factory.tar.gz";
const remoteDir = process.env.ERA_REMOTE_DIR || "/opt/era-media-factory";
const backendPort = process.env.ERA_BACKEND_PORT || "18000";
const frontendPort = process.env.ERA_FRONTEND_PORT || "13000";
const composeEnv = `BACKEND_PORT=${backendPort} FRONTEND_PORT=${frontendPort} DEV_MODE=true BACKEND_CORS_ORIGINS=http://localhost:${frontendPort},http://${host}:${frontendPort}`;

if (!password) throw new Error("ERA_SSH_PASSWORD is required.");
if (!fs.existsSync(archive)) throw new Error(`Archive is missing: ${archive}`);

const conn = new Client();

function connect() {
  return new Promise((resolve, reject) => {
    conn.on("ready", resolve).on("error", reject).connect({ host, username, password, readyTimeout: 30000 });
  });
}

function exec(command, label) {
  return new Promise((resolve, reject) => {
    conn.exec(command, { pty: false }, (err, stream) => {
      if (err) return reject(err);
      let stdout = "";
      let stderr = "";
      stream.on("close", (code) => {
        console.log(`\n## ${label}\nexit=${code}`);
        if (stdout.trim()) console.log(stdout.trim().slice(-5000));
        if (stderr.trim()) console.error(stderr.trim().slice(-5000));
        resolve(code);
      });
      stream.on("data", (data) => (stdout += data.toString()));
      stream.stderr.on("data", (data) => (stderr += data.toString()));
    });
  });
}

function upload(localPath, remotePath) {
  return new Promise((resolve, reject) => {
    conn.sftp((err, sftp) => {
      if (err) return reject(err);
      sftp.fastPut(localPath, remotePath, (putErr) => (putErr ? reject(putErr) : resolve()));
    });
  });
}

await connect();
console.log("connected");
await upload(archive, "/tmp/era-media-factory.tar.gz");
console.log("uploaded");

const commands = [
  ["prepare", `mkdir -p ${remoteDir}`],
  ["extract", `cd ${remoteDir} && find . -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} + && tar -xzf /tmp/era-media-factory.tar.gz -C ${remoteDir}`],
  ["ensure app secret", `cd ${remoteDir} && touch .env && grep -q '^APP_SECRET_KEY=' .env || printf '\\nAPP_SECRET_KEY=%s\\n' "$(openssl rand -hex 32)" >> .env`],
  ["compose up", `cd ${remoteDir} && ${composeEnv} docker compose up --build -d --remove-orphans`],
  ["compose ps", `cd ${remoteDir} && ${composeEnv} docker compose ps`],
  ["backend health", `for i in $(seq 1 60); do curl -fsS http://localhost:${backendPort}/health && exit 0; sleep 2; done; exit 1`],
  ["frontend status", `for i in $(seq 1 60); do curl -fsS http://localhost:${frontendPort}/api/status && exit 0; sleep 2; done; exit 1`],
  ["migrations", `cd ${remoteDir} && ${composeEnv} docker compose exec -T backend alembic current`],
  ["smoke control plane", `cd ${remoteDir} && BACKEND_PORT=${backendPort} ${composeEnv} docker compose exec -T backend python -m app.smoke_control_plane`],
  ["smoke secrets", `cd ${remoteDir} && BACKEND_PORT=${backendPort} ${composeEnv} docker compose exec -T backend python -m app.smoke_secrets`],
  ["smoke real llm dry-run", `cd ${remoteDir} && BACKEND_PORT=${backendPort} ${composeEnv} docker compose exec -T backend python -m app.smoke_real_llm_dry_run`],
  ["public frontend", `curl -fsS http://${host}:${frontendPort}/api/status`],
  ["public backend", `curl -fsS http://${host}:${backendPort}/health`],
];

for (const [label, command] of commands) {
  const code = await exec(command, label);
  if (code !== 0) {
    conn.end();
    process.exit(code);
  }
}

conn.end();
