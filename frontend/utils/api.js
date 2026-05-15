import axios from "axios";


const isServer = typeof window === "undefined";
// 나중에 FastAPI 서버 주소로 바꾸면 됨 (지금은 localhost 기준)
const api = axios.create({
  baseURL: isServer ? "http://xtock-backend:8000" : "http://localhost:8000",
});

export default api;
