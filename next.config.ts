import type { NextConfig } from 'next';

process.env.COPILOTKIT_TELEMETRY_DISABLED ??= 'true';

const config: NextConfig = {
  agentRules: false,
  output: 'standalone',
  poweredByHeader: false,
  reactStrictMode: true,
};
export default config;
