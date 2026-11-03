import type { NextConfig } from 'next';

process.env.COPILOTKIT_TELEMETRY_DISABLED ??= 'true';

const config: NextConfig = {
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: true,
};
export default config;
