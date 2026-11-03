// icon.ico (PNG-embedded entries) + icon.png from the authorized RedRise logo PNGs.
// usage: node make-ico.mjs <brand dir> <out icons dir>
import fs from "node:fs";
import path from "node:path";

const [brand, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const sizes = [16, 24, 32, 48, 64, 128, 256];
const pngs = sizes.map((s) => fs.readFileSync(path.join(brand, `redrise-icon-${s}x${s}.png`)));
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0); header.writeUInt16LE(1, 2); header.writeUInt16LE(sizes.length, 4);
const dir = Buffer.alloc(16 * sizes.length);
let offset = 6 + dir.length;
sizes.forEach((s, i) => {
  const e = i * 16;
  dir.writeUInt8(s >= 256 ? 0 : s, e); dir.writeUInt8(s >= 256 ? 0 : s, e + 1);
  dir.writeUInt16LE(1, e + 4); dir.writeUInt16LE(32, e + 6);
  dir.writeUInt32LE(pngs[i].length, e + 8); dir.writeUInt32LE(offset, e + 12);
  offset += pngs[i].length;
});
fs.writeFileSync(path.join(out, "icon.ico"), Buffer.concat([header, dir, ...pngs]));
fs.copyFileSync(path.join(brand, "redrise-icon-512x512.png"), path.join(out, "icon.png"));
console.log("icons written to", out);
