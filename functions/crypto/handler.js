"use strict";

const crypto = require("crypto");

function generate(length) {
  const characters = "abcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < length; i++) {
    const randomIndex = Math.floor(Math.random() * characters.length);
    result += characters[randomIndex];
  }
  return result;
}

module.exports = async (event, context) => {
  const req = typeof event.body === "object" ? event.body : JSON.parse(event.body);
  const lengthOfMessage = req.length_of_message;
  const numOfIterations = req.num_of_iterations;

  const start = Date.now();
  const message = generate(lengthOfMessage);

  // 128-bit key (16 bytes)
  const KEY = Buffer.from([
    0xa1, 0xf6, 0x25, 0x8c, 0x87, 0x7d, 0x5f, 0xcd, 0x89, 0x64, 0x48, 0x45, 0x38, 0xbf, 0xc9, 0x2c,
  ]);

  let plaintext = "";
  for (let loops = 0; loops < numOfIterations; loops++) {
    const aes = crypto.createCipheriv("aes-128-ctr", KEY, Buffer.alloc(16, 0)); // Use an all-zero IV for CTR mode
    const ciphertext = aes.update(message, "utf8", "hex") + aes.final("hex");

    const decipher = crypto.createDecipheriv("aes-128-ctr", KEY, Buffer.alloc(16, 0));
    plaintext = decipher.update(ciphertext, "hex", "utf8") + decipher.final("utf8");
  }
  const latency = Date.now() - start;

  return context
    .status(200)
    .succeed({
      latency: latency / 1000,
      data: plaintext,
    });
};
