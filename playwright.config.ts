import {defineConfig, devices} from '@playwright/test';
export default defineConfig({
  webServer: process.env.CI ? {command: 'npm run start', url: 'http://127.0.0.1:8765', timeout: 120000,
    env: {PROOF_DATA_DIR: '.test-data', NIMBLE_API_KEY: ''}} : undefined,
  testDir: './tests/browser', workers: 1, timeout: 45000,
  use: {baseURL: process.env.PROOF_UI_URL || 'http://127.0.0.1:8765', channel: process.env.CI ? undefined : 'chrome', trace: 'retain-on-failure'},
  projects: [{name: 'desktop', use: {...devices['Desktop Chrome'], viewport: {width: 1440, height: 1050}}},
             {name: 'mobile', use: {...devices['iPhone 13'], defaultBrowserType: 'chromium'}}],
});
