import os from 'os';

const getLocalIPv4s = () => {
  const interfaces = os.networkInterfaces();
  const ips = [];
  for (const name of Object.keys(interfaces)) {
    for (const net of interfaces[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        ips.push(net.address);
      }
    }
  }
  return ips;
};

/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: getLocalIPv4s(),
};

export default nextConfig;
