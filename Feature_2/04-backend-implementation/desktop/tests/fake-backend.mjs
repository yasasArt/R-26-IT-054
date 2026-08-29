import { createServer } from "node:http";

const port = Number(process.env.GARMENT_COUNTER_PORT);
const token = process.env.GARMENT_COUNTER_API_TOKEN;

const server = createServer((request, response) => {
  if (request.url === "/health") {
    response.writeHead(200, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ ready: true }));
    return;
  }
  if (request.url === "/api/models/status") {
    const authenticated = request.headers.authorization === `Bearer ${token}`;
    response.writeHead(authenticated ? 200 : 401, { "Content-Type": "application/json" });
    response.end(JSON.stringify({ authenticated, tokenLength: token?.length ?? 0 }));
    return;
  }
  response.writeHead(404, { "Content-Type": "application/json" });
  response.end(JSON.stringify({ detail: "not found" }));
});

server.listen(port, "127.0.0.1");
process.on("SIGTERM", () => server.close(() => process.exit(0)));

