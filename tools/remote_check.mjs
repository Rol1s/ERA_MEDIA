import fs from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { Client } = require("ssh2");

const host = process.env.ERA_SSH_HOST;
const username = process.env.ERA_SSH_USER || "root";
const password = process.env.ERA_SSH_PASSWORD;
const archive = process.env.ERA_ARCHIVE || "era-media-factory.tar.gz";
const remoteDir = process.env.ERA_REMOTE_DIR || "/opt/era-media-factory";
const backendPort = process.env.ERA_BACKEND_PORT || "18000";
const frontendPort = process.env.ERA_FRONTEND_PORT || "13000";
const composeEnv = `BACKEND_PORT=${backendPort} FRONTEND_PORT=${frontendPort} DEV_MODE=true BACKEND_CORS_ORIGINS=http://localhost:${frontendPort},http://${host}:${frontendPort}`;

if (!host || !password) {
  throw new Error("ERA_SSH_HOST and ERA_SSH_PASSWORD are required.");
}

const conn = new Client();

function connect() {
  return new Promise((resolve, reject) => {
    conn
      .on("ready", resolve)
      .on("error", reject)
      .connect({ host, username, password, readyTimeout: 30000 });
  });
}

function exec(command) {
  return new Promise((resolve, reject) => {
    conn.exec(command, { pty: false }, (err, stream) => {
      if (err) {
        reject(err);
        return;
      }
      let stdout = "";
      let stderr = "";
      stream
        .on("close", (code) => {
          resolve({ code, stdout, stderr });
        })
        .on("data", (data) => {
          stdout += data.toString();
        });
      stream.stderr.on("data", (data) => {
        stderr += data.toString();
      });
    });
  });
}

function upload(localPath, remotePath) {
  return new Promise((resolve, reject) => {
    conn.sftp((err, sftp) => {
      if (err) {
        reject(err);
        return;
      }
      sftp.fastPut(localPath, remotePath, (putErr) => {
        if (putErr) {
          reject(putErr);
          return;
        }
        resolve();
      });
    });
  });
}

function printResult(label, result) {
  console.log(`\n## ${label}`);
  console.log(`exit=${result.code}`);
  const out = result.stdout.trim();
  const err = result.stderr.trim();
  if (out) console.log(out.slice(-4000));
  if (err) console.error(err.slice(-4000));
}

await connect();
console.log("connected");

for (const [label, command] of [
  ["system", "uname -a && docker --version && docker compose version"],
  ["prepare", `mkdir -p ${remoteDir}`],
]) {
  const result = await exec(command);
  printResult(label, result);
  if (result.code !== 0) process.exitCode = result.code;
}

await upload(archive, "/tmp/era-media-factory.tar.gz");
console.log("uploaded");

const commands = [
  ["compose down", `cd ${remoteDir} && docker compose down --remove-orphans -v || true`],
  ["extract", `rm -rf ${remoteDir}/* && tar -xzf /tmp/era-media-factory.tar.gz -C ${remoteDir}`],
  ["compose config", `cd ${remoteDir} && ${composeEnv} docker compose config`],
  ["compose up", `cd ${remoteDir} && ${composeEnv} docker compose up --build -d`],
  ["compose ps", `cd ${remoteDir} && ${composeEnv} docker compose ps`],
  ["health", `curl -fsS http://localhost:${backendPort}/health`],
  ["frontend proxy status", `for i in $(seq 1 30); do curl -fsS http://localhost:${frontendPort}/api/status && exit 0; sleep 2; done; exit 1`],
  ["org agents", `curl -fsS http://localhost:${frontendPort}/api/org/agents`],
  ["goals", `curl -fsS http://localhost:${frontendPort}/api/goals`],
  ["routines", `curl -fsS http://localhost:${frontendPort}/api/routines`],
  ["channels", `curl -fsS http://localhost:${backendPort}/api/channels`],
  [
    "create source",
    `curl -fsS -X POST http://localhost:${backendPort}/api/sources -H 'Content-Type: application/json' -d '{"name":"Manual Test Source","url":"https://example.com/rss","type":"manual","language":"ru","trust_score":0.8,"status":"active"}'`,
  ],
  [
    "update source",
    `curl -fsS -X PATCH http://localhost:${backendPort}/api/sources/1 -H 'Content-Type: application/json' -d '{"trust_score":0.9}'`,
  ],
  ["list sources", `curl -fsS http://localhost:${backendPort}/api/sources`],
  ["delete source", `curl -fsS -X DELETE http://localhost:${backendPort}/api/sources/1 -i`],
  [
    "create topic",
    `curl -fsS -X POST http://localhost:${backendPort}/api/topics -H 'Content-Type: application/json' -d '{"title":"AI agents change small business operations","url":"https://example.com/ai-agents","summary":"A practical test topic for ERA AI about why agent orchestration matters.","raw_text":"AI agents can discover topics, research facts, draft useful posts and route them to channels when bounded by attempts and review states.","status":"new"}'`,
  ],
  [
    "update topic",
    `curl -fsS -X PATCH http://localhost:${backendPort}/api/topics/1 -H 'Content-Type: application/json' -d '{"summary":"Updated practical test topic for ERA AI."}'`,
  ],
  ["run pipeline", `curl -fsS -X POST http://localhost:${backendPort}/api/topics/1/run-pipeline`],
  ["rewrite post", `curl -fsS -X POST http://localhost:${backendPort}/api/posts/1/rewrite -H 'Content-Type: application/json' -d '{"notes":["make_more_useful"]}'`],
  ["approve post", `curl -fsS -X POST http://localhost:${backendPort}/api/posts/1/approve`],
  ["schedule post", `curl -fsS -X POST http://localhost:${backendPort}/api/posts/1/schedule -H 'Content-Type: application/json' -d '{}'`],
  ["posts", `curl -fsS http://localhost:${backendPort}/api/posts`],
  ["tasks", `curl -fsS http://localhost:${backendPort}/api/tasks`],
  ["agent runs", `curl -fsS http://localhost:${backendPort}/api/agent-runs`],
  ["demo data", `curl -fsS -X POST http://localhost:${frontendPort}/api/dev/demo-data`],
  ["cost summary", `curl -fsS http://localhost:${frontendPort}/api/costs/summary`],
  ["activity", `curl -fsS http://localhost:${frontendPort}/api/activity`],
  ["smoke test", `cd ${remoteDir} && BACKEND_PORT=${backendPort} docker compose exec -T backend python -m app.smoke_test`],
];

for (const [label, command] of commands) {
  const result = await exec(command);
  printResult(label, result);
  if (result.code !== 0) {
    process.exitCode = result.code;
    break;
  }
}

conn.end();
