const TOKEN_KEY = "computex_token";
const USER_KEY = "computex_user";

export function saveSession(name, token) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, name);
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  return localStorage.getItem(USER_KEY);
}