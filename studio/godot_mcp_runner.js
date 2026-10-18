#!/usr/bin/env node
/**
 * Standalone Godot MCP Tool Runner for PirateUI
 * Bridges PirateUI directly to D:/godot-mcp ToolRegistry
 */

import { pathToFileURL } from 'url';
import { existsSync } from 'fs';

const GODOT_MCP_DIR = 'D:/godot-mcp';
const DEFAULT_GODOT_PATH = 'D:/Godot_v4.6.1-stable_mono_win64/Godot_v4.6.1-stable_mono_win64_console.exe';

process.env.GODOT_PATH = process.env.GODOT_PATH || DEFAULT_GODOT_PATH;

async function run() {
  const [,, toolName, rawArgs] = process.argv;
  if (!toolName) {
    console.error(JSON.stringify({ error: "Missing toolName argument" }));
    process.exit(1);
  }

  const registryPath = `${GODOT_MCP_DIR}/build/tools/ToolRegistry.js`;
  if (!existsSync(registryPath)) {
    console.error(JSON.stringify({ error: `Godot MCP not built at ${registryPath}` }));
    process.exit(1);
  }

  try {
    const registryUrl = pathToFileURL(registryPath).href;
    const { getToolHandler, getRegisteredToolNames } = await import(registryUrl);

    if (toolName === "list_tools") {
      const tools = getRegisteredToolNames();
      console.log(JSON.stringify({ status: "success", tools }));
      return;
    }

    const handler = getToolHandler(toolName);
    if (!handler) {
      console.error(JSON.stringify({ error: `Unknown Godot MCP tool: ${toolName}`, available: getRegisteredToolNames() }));
      process.exit(1);
    }

    const args = rawArgs ? JSON.parse(rawArgs) : {};
    const result = await handler(args);
    console.log(JSON.stringify({ status: "success", tool: toolName, result }));
  } catch (err) {
    console.error(JSON.stringify({ error: err.message, stack: err.stack }));
    process.exit(1);
  }
}

run();
