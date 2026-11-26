const {createServer} = require("node:http");
const handle = require("./handler.cjs");
const port = Number(process.env.PORT || 8787);
createServer((req, res) => {
  if (req.url === "/api/mcp") return handle(req, res);
  res.writeHead(404).end();
}).listen(port, "127.0.0.1", () => console.log("Ocean MCP listening on http://127.0.0.1:" + port + "/api/mcp"));
