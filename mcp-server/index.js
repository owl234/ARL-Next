#!/usr/bin/env node

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");
const axios = require("axios");
const host = process.env.ARL_HOST;
const token = process.env.ARL_TOKEN;

if (!host || !token) {
  console.error("Error: Environment variables ARL_HOST and ARL_TOKEN are required.");
  process.exit(1);
}

const https = require("https");

const apiClient = axios.create({
  baseURL: `${host}/api`,
  headers: {
    "Token": token
  },
  timeout: 10000,
  httpsAgent: new https.Agent({  
    rejectUnauthorized: false,
    keepAlive: true
  })
});

function trimPayload(data) {
  if (data === null || data === undefined) return data;
  if (Array.isArray(data)) {
    return data.map(trimPayload);
  } else if (typeof data === 'object') {
    const trimmed = {};
    for (const [key, value] of Object.entries(data)) {
      // 过滤容易导致载荷过大的无用字段
      if (['body', 'header', 'headers', 'favicon', 'raw_data', 'html', 'icon', 'cert_raw', 'ssl_cert'].includes(key)) {
        continue;
      }
      // 截断过长字符串
      if (typeof value === 'string' && value.length > 500) {
        trimmed[key] = value.substring(0, 500) + '...[TRUNCATED]';
      } else {
        trimmed[key] = trimPayload(value);
      }
    }
    return trimmed;
  }
  return data;
}

const server = new Server(
  {
    name: "arl-next-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Helper for formatting API responses with pagination note
function formatResponse(responseData) {
  const trimmed = trimPayload(responseData);
  let resultStr = JSON.stringify(trimmed, null, 2);
  if (responseData && responseData.page && responseData.size && responseData.total !== undefined) {
    const totalPages = Math.ceil(responseData.total / responseData.size) || 1;
    resultStr += `\n\n[System Note: 当前显示第 ${responseData.page} 页，共 ${totalPages} 页 (总计 ${responseData.total} 条数据)。如果需要查看更多数据，请在下一次调用此 Tool 时传入参数 page=${responseData.page + 1}]`;
  }
  return resultStr;
}

// Define tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_assets",
        description: "在 ARL-Next 资产库中搜索发现的资产。当你需要查询网站(site)、IP、域名(domain)、证书(cert)、开放端口/协议服务(service)时使用此工具。必需参数: assetType。支持通过 query 参数模糊搜索组件名称（例如 query='nginx' 或 '1.1.1.1'）。",
        inputSchema: {
          type: "object",
          properties: {
            assetType: {
              type: "string",
              description: "要搜索的资产类型。可选值：'site' (网站), 'ip' (IP地址), 'domain' (域名), 'cert' (证书), 'service' (开放端口/服务), 'asset_wih' (WIH信息)",
              enum: ["site", "ip", "domain", "cert", "service", "asset_wih"]
            },
            query: {
              type: "string",
              description: "模糊搜索关键词（例如 'nginx', '1.1.1.1', 'example.com'）"
            },
            page: {
              type: "number",
              description: "页码 (默认 1)"
            },
            size: {
              type: "number",
              description: "单页数据量 (默认 10，最大 50)"
            }
          },
          required: ["assetType"]
        }
      },
      {
        name: "search_vulns",
        description: "在 ARL 漏洞库中搜索和查询系统发现的安全漏洞。支持按危险等级(vuln_severity)过滤，或按漏洞名称(query)模糊搜索。",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description: "漏洞名称或详细信息的模糊搜索关键词。"
            },
            vuln_severity: {
              type: "string",
              description: "按严重级别过滤。",
              enum: ["critical", "high", "medium", "low"]
            },
            page: {
              type: "number",
              description: "页码 (默认 1)"
            },
            size: {
              type: "number",
              description: "单页数据量 (默认 10，最大 50)"
            }
          }
        }
      },
      {
        name: "get_dashboard_summary",
        description: "获取整个 ARL 系统当前的运行状态与统计大盘数据（包括资产总数、运行中的任务数、各类漏洞数量统计、系统性能等）。适合用于生成每日系统概览或战报。",
        inputSchema: {
          type: "object",
          properties: {}
        }
      },
      {
        name: "get_tasks",
        description: "获取最近的资产发现与漏洞扫描任务列表及其执行状态（运行中、已完成、等待中等）。",
        inputSchema: {
          type: "object",
          properties: {
            page: { type: "number", description: "页码 (默认 1)" },
            size: { type: "number", description: "单页数据量 (默认 10)" }
          }
        }
      },
      {
        name: "search_icp_tasks",
        description: "查询最近发起的 ICP 备案信息拉取及企业架构分析任务。",
        inputSchema: {
          type: "object",
          properties: {
            name: { type: "string", description: "按任务名称过滤" },
            target: { type: "string", description: "按目标对象（如公司名称）过滤" },
            status: { type: "string", description: "任务状态" },
            page: { type: "number", description: "页码 (默认 1)" },
            size: { type: "number", description: "单页数据量 (默认 10)" }
          }
        }
      },
      {
        name: "search_icp_assets",
        description: "深度挖掘指定 ICP 任务获取到的子资产维度数据（如公众号、小程序、软件著作、商标等）或全局查询。",
        inputSchema: {
          type: "object",
          properties: {
            task_id: { type: "string", description: "关联的 ICP 任务 ID（不传则全局检索）" },
            query_type: { 
              type: "string", 
              description: "查询子维度。可选：'web' (网站), 'app' (应用), 'mapp' (小程序), 'kapp' (快应用), 'invest' (投资机构), 'trademark' (商标), 'wechat' (微信公号), 'weibo' (微博)",
              enum: ["web", "app", "mapp", "kapp", "invest", "trademark", "wechat", "weibo"]
            },
            page: { type: "number", description: "页码 (默认 1)" },
            size: { type: "number", description: "单页数据量 (默认 10，最大 50)" }
          },
          required: ["query_type"]
        }
      }
    ],
  };
});
// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  
  try {
    if (name === "search_assets") {
      const { assetType, query, page = 1, size = 10 } = args;
      const allowedAssets = ["site", "ip", "domain", "cert", "service", "asset_wih"];
      if (!allowedAssets.includes(assetType)) {
        return { content: [{ type: "text", text: `Error: Invalid assetType '${assetType}'` }], isError: true };
      }
      const safeSize = Math.min(size, 50);
      const response = await apiClient.get(`/${assetType}/`, { params: { page, size: safeSize, query } });
      return { content: [{ type: "text", text: formatResponse(response.data) }] };
    }

    if (name === "search_vulns") {
      const { query, vuln_severity, page = 1, size = 10 } = args;
      const safeSize = Math.min(size, 50);
      const response = await apiClient.get(`/vuln/`, { params: { page, size: safeSize, query, vuln_severity } });
      return { content: [{ type: "text", text: formatResponse(response.data) }] };
    }

    if (name === "get_dashboard_summary") {
      const statsRes = await apiClient.get(`/dashboard/stats`);
      const sysinfoRes = await apiClient.get(`/dashboard/sysinfo`);
      const result = {
        stats: statsRes.data,
        sysinfo: sysinfoRes.data
      };
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }

    if (name === "get_tasks") {
      const { page = 1, size = 10 } = args;
      const response = await apiClient.get(`/task/`, { params: { page, size } });
      return { content: [{ type: "text", text: formatResponse(response.data) }] };
    }

    if (name === "search_icp_tasks") {
      const { page = 1, size = 10, name: taskName, target, status } = args;
      const response = await apiClient.get(`/icp/task`, { params: { page, size, name: taskName, target, status } });
      return { content: [{ type: "text", text: formatResponse(response.data) }] };
    }

    if (name === "search_icp_assets") {
      const { task_id, query_type, page = 1, size = 10 } = args;
      const allowedTypes = ["web", "app", "mapp", "kapp", "invest", "trademark", "wechat", "weibo"];
      if (!allowedTypes.includes(query_type)) {
        return { content: [{ type: "text", text: `Error: Invalid query_type '${query_type}'` }], isError: true };
      }
      const safeSize = Math.min(size, 50);
      const response = await apiClient.get(`/icp/asset`, { params: { page, size: safeSize, task_id, query_type } });
      return { content: [{ type: "text", text: formatResponse(response.data) }] };
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (error) {
    return {
      content: [{ type: "text", text: `API Request Failed: ${error.message}\n${error.response?.data ? JSON.stringify(error.response.data) : ''}` }],
      isError: true
    };
  }
});
async function run() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ARL-Next MCP Server running on stdio");
}

run().catch((error) => {
  console.error("Fatal error running MCP server:", error);
  process.exit(1);
});
