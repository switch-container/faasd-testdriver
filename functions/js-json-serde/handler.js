"use strict";

const fs = require('fs').promises;
const path = require("path");

const AVAILABLE_NAMES = ["1", "2", "3", "4", "5"];

module.exports = async (event, context) => {
  const start = Date.now();
  let name = "1";
  try {
    const req = typeof event.body === "object" ? event.body : JSON.parse(event.body);
    if ("name" in req) {
      name = req.name;
    }
  } catch {}
  if (!AVAILABLE_NAMES.includes(name)) {
    name = "1";
  }

  const p = path.join(__dirname, "files", `${name}.json`);
  const data = await fs.readFile(p, "utf8");
  const j = JSON.parse(data);
  const str_j = JSON.stringify(j, null, 4)

  const latency = Date.now() - start;

  return context
    .status(200)
    .succeed({
      latency: latency / 1000,
      data: p,
    });
};
