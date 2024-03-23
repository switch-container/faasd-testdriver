"use strict";

const path = require("path");
const sharp = require("sharp");

module.exports = async (event, context) => {
  let image_id = 0;
  try {
    const req = typeof event.body === "object" ? event.body : JSON.parse(event.body);
    if ("image_id" in req) {
      image_id = req.image_id;
    }
  } catch {}
  const start = Date.now();
  let p;
  if (image_id == 0) {
    p = path.join(__dirname, "images", "image.jpg");
  } else {
    p = path.join(__dirname, "images", "image2.jpg");
  }

  const image = sharp(p);
  await Promise.all([
    image.flip().toFile("/run/flip-top-bottom.jpg"),
    image.flop().toFile("/run/flop-left-right.jpg"),
    image.rotate(90).toFile("/run/rotate-90.jpg"),
    image.rotate(180).toFile("/run/rotate-180.jpg"),
    image.rotate(270).toFile("/run/rotate-270.jpg"),
  ]);

  const latency = Date.now() - start;

  return context
    .status(200)
    .succeed({
      latency: latency / 1000,
    });
};
