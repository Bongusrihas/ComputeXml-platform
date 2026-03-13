import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { saveSession } from "../lib/session";

export default function LoginPage() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.post("/auth/login", { name: name.trim() });
      saveSession(res.data.name, res.data.token);
      navigate("/landing");
    } catch (err) {
      setError(err.response?.data?.error || "Login failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="card" style={{ maxWidth: 520 }}>
        <h1>Enter Name</h1>
        <p className="note">Your name and login token will be stored in MongoDB.</p>
        <form className="grid" onSubmit={submit}>
          <input
            placeholder="Your name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <button disabled={loading || !name.trim()} type="submit">
            {loading ? "Please wait..." : "Continue"}
          </button>
          {error && <p style={{ color: "#bf1f2f" }}>{error}</p>}
        </form>
      </div>
    </div>
  );
}