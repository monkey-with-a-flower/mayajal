/** @type {import("next").NextConfig} */
const nextConfig = {
  output: "standalone",
  allowedDevOrigins: ["192.168.1.33", "*.local"],
};

module.exports = nextConfig;
