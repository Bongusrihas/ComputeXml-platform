import { useNavigate } from "react-router-dom";
import { getUser } from "../lib/session";

export default function LandingPage() {
  const navigate = useNavigate();
  const user = getUser();

  return (
    <div className="page">
      <div className="card" style={{ maxWidth: 700, textAlign: "center" }}>
        <h1>Computex ML Platform</h1>
        <p className="note">Signed in as {user || "User"}</p>
        <button onClick={() => navigate("/upload")}>Continue</button>
      </div>
    </div>
  );
}