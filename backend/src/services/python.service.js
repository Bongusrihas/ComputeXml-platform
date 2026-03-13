import axios from "axios";
import CircuitBreaker from "opossum";

const pythonUrl = process.env.PYTHON_SERVICE_URL || "http://localhost:8000";

async function dispatchToPython(payload) {
  const response = await axios.post(`${pythonUrl}/schedule`, payload, {
    timeout: 30000
  });
  return response.data;
}

const breaker = new CircuitBreaker(dispatchToPython, {
  timeout: 35000,
  errorThresholdPercentage: 50,
  resetTimeout: 12000
});

breaker.fallback(() => ({
  status: "degraded",
  message: "Python service unavailable."
}));

export async function callPythonService(payload) {
  return breaker.fire(payload);
}

export async function callPythonPredict(payload) {
  const response = await axios.post(`${pythonUrl}/predict`, payload, {
    timeout: 15000
  });
  return response.data;
}