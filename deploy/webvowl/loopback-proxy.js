"use strict";

const http = require("http");

const upstreamHost = "webvowl";
const upstreamPort = 8080;
const allowedHostHeaders = new Set([
  "127.0.0.1:8080",
  "localhost:8080",
]);
const allowedMethods = new Set(["GET", "HEAD", "POST"]);

function reject(response, statusCode, message) {
  response.writeHead(statusCode, {
    "content-type": "text/plain; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(`${message}\n`);
}

const server = http.createServer((request, response) => {
  const host = String(request.headers.host || "").toLowerCase();
  const rawUrl = String(request.url || "");
  if (!allowedHostHeaders.has(host)) {
    reject(response, 421, "Loopback Host header required");
    return;
  }
  if (!allowedMethods.has(request.method) || !rawUrl.startsWith("/") || rawUrl.startsWith("//")) {
    reject(response, 403, "Forward-proxy requests are forbidden");
    return;
  }

  const headers = {
    accept: request.headers.accept || "*/*",
    "accept-encoding": request.headers["accept-encoding"] || "identity",
    host: `${upstreamHost}:${upstreamPort}`,
  };
  for (const name of ["content-type", "content-length", "if-modified-since", "if-none-match", "range", "user-agent"]) {
    if (request.headers[name] !== undefined) {
      headers[name] = request.headers[name];
    }
  }
  const upstream = http.request(
    {
      hostname: upstreamHost,
      port: upstreamPort,
      method: request.method,
      path: request.url,
      headers,
    },
    (upstreamResponse) => {
      response.writeHead(upstreamResponse.statusCode, upstreamResponse.headers);
      upstreamResponse.pipe(response);
    }
  );

  upstream.on("error", () => {
    if (!response.headersSent) {
      response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
    }
    response.end("WebVOWL upstream unavailable\n");
  });
  request.pipe(upstream);
});

// Explicitly reject HTTP CONNECT and protocol upgrades.  The relay has one
// immutable upstream and cannot be repurposed as a generic HTTP/WebSocket
// forwarder even though its bridge is needed for loopback port publication.
server.on("connect", (_request, socket) => {
  socket.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
});
server.on("upgrade", (_request, socket) => {
  socket.end("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
});

server.listen(8080, "0.0.0.0");
