import axios from "axios";

// 나중에 FastAPI 서버 주소로 바꾸면 됨 (지금은 localhost 기준)
const api = axios.create({
  baseURL: "http://localhost:8000",
});

export default api;
