const {StreamableHTTPServerTransport} = require("@modelcontextprotocol/sdk/server/streamableHttp.js");
const {createServer} = require("./server.cjs");

const bodyLimit = 3 * 1024 * 1024;
function reject(res, status, message) {
  res.writeHead(status, {"Content-Type": "application/json"});
  res.end(JSON.stringify({jsonrpc: "2.0", id: null, error: {code: -32000, message}}));
}

function makeHandler(fetcher = fetch) {
  return async function handle(req, res) {
    res.setHeader("Cache-Control", "private, no-store");
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("X-Robots-Tag", "noindex");
    if (req.headers.origin !== undefined && req.headers.origin !== "https://ocean.sig.ai") {
      return reject(res, 403, "This browser origin is not allowed.");
    }
    if (req.method !== "POST") {
      res.setHeader("Allow", "POST");
      return reject(res, 405, "Use an MCP client with Streamable HTTP POST.");
    }
    if (Number(req.headers["content-length"]) > bodyLimit) return reject(res, 413, "Request is too large.");

    const server = createServer(fetcher);
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, enableJsonResponse: true, maxRequestBodySize: bodyLimit
    });
    res.once("close", () => { void server.close().catch(() => {}); });
    try {
      await server.connect(transport);
      // Hosting adapters may supply a parsed body. Plain Node requests use the SDK's bounded stream reader.
      await transport.handleRequest(req, res, req.body);
    } catch {
      if (!res.headersSent) reject(res, 400, "The MCP request could not be processed.");
      else if (!res.writableEnded) res.end();
    }
  };
}

module.exports = makeHandler();
module.exports.makeHandler = makeHandler;
