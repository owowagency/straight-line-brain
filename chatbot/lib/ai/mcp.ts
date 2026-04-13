import { createMCPClient, type MCPClient } from "@ai-sdk/mcp";

const MCP_SERVER_URL =
  process.env.MCP_SERVER_URL ?? "http://localhost:8001/mcp";

let client: MCPClient | null = null;

async function getClient(): Promise<MCPClient> {
  if (!client) {
    client = await createMCPClient({
      transport: {
        type: "http",
        url: MCP_SERVER_URL,
      },
      name: "digitaal-brein-chatbot",
    });
  }
  return client;
}

export async function getBreinTools() {
  const mcpClient = await getClient();
  return mcpClient.tools();
}

export async function closeMCPClient() {
  if (client) {
    await client.close();
    client = null;
  }
}
