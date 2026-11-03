import {cpSync, existsSync} from 'node:fs';

const root = new URL('../', import.meta.url);
const standalone = new URL('.next/standalone/', root);
const entry = new URL('server.js', standalone);
if (!existsSync(entry)) {
  console.error('Run npm run build before npm start.');
  process.exit(1);
}

// Next.js leaves these assets out of standalone output for CDN deployments.
cpSync(new URL('.next/static/', root), new URL('.next/static/', standalone), {recursive: true});
if (existsSync(new URL('public/', root))) {
  cpSync(new URL('public/', root), new URL('public/', standalone), {recursive: true});
}
process.env.HOSTNAME = '127.0.0.1';
process.env.PORT ||= '8765';
process.env.COPILOTKIT_TELEMETRY_DISABLED ??= 'true';
await import(entry.href);
