const os = require("node:os");

const lanAddresses = Object.values(os.networkInterfaces())
  .flat()
  .filter(
    (address) =>
      address &&
      address.family === "IPv4" &&
      !address.internal,
  )
  .map((address) => address.address);

/** @type {import("next").NextConfig} */
const nextConfig = {
  output: "standalone",
  // Next protects development assets from cross-origin requests. Include every
  // active LAN address so remote browsers can load /_next CSS and JavaScript
  // even when DHCP changes the host address between launches.
  allowedDevOrigins: [...new Set([...lanAddresses, "*.local"])],
};

module.exports = nextConfig;
