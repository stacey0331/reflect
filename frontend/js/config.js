const isLocal = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const API_ORIGIN = isLocal ? "http://localhost:8000" : "";

export const API_BASE_URL = API_ORIGIN;
export const API_BASE = `${API_ORIGIN}/api`;