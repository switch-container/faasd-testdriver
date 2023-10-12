"use strict";

const path = require("path");
const sharp = require("sharp");

module.exports = async (event, context) => {
  const start = Date.now();

  const image = sharp(path.join(__dirname, "images", "image.jpg"));
  await Promise.all([
    image.flip().toFile("/tmp/flip-top-bottom.jpg"),
    image.flop().toFile("/tmp/flop-left-right.jpg"),
    image.rotate(90).toFile("/tmp/rotate-90.jpg"),
    image.rotate(180).toFile("/tmp/rotate-180.jpg"),
    image.rotate(270).toFile("/tmp/rotate-270.jpg"),
  ]);

  const latency = Date.now() - start;

  return context
    .status(200)
    .succeed({
      latency: latency / 1000,
    });
};
