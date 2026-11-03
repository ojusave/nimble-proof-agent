// The only server configuration for the Python API. Never exposed to the browser.
export const backendUrl = process.env.PROOF_BACKEND_URL || 'http://127.0.0.1:8767';
