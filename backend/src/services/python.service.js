import axios from "axios";

const pythonUrl = process.env.PYTHON_SERVICE_URL || "http://localhost:8000/api";

export async function callPythonService(payload) {
  const response = await axios.post(`${pythonUrl}/schedule`, payload, {
    timeout: 60000
  });
  return response.data;
}

export async function callPythonPredict(payload) {
  const response = await axios.post(`${pythonUrl}/predict`, payload, {
    timeout: 15000
  });
  return response.data;
}
