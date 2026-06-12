"use client";
import { useState } from "react";
import api from "../utils/api"; // [필수] axios 인스턴스 import
import { User, Lock, Mail, ArrowRight } from 'lucide-react';

export default function LoginPage({ onLogin }) {
  const [view, setView] = useState("login"); 
  const [isLoading, setIsLoading] = useState(false);

  // 입력값 상태 관리
  const [formData, setFormData] = useState({
    username: "",
    email: "",
    password: ""
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (view === 'signup') {
        // [회원가입 요청]
        const res = await api.post("/api/register", {
          username: formData.username,
          email: formData.email,
          password: formData.password
        });

        if (res.data.success) {
          alert("가입을 환영합니다! 로그인해주세요.");
          setView('login');
          setFormData({ ...formData, password: "" }); // 비번 초기화
        } else {
          alert(res.data.msg || "회원가입 실패");
        }

      } else if (view === 'login') {
        // [로그인 요청]
        const res = await api.post("/api/login", {
          email: formData.email,
          password: formData.password
        });

        if (res.data.success) {
          // 성공 시 부모(page.js)에게 유저 정보 전달
          onLogin(res.data.user);
        } else {
          alert(res.data.msg || "로그인 실패");
        }
      } else if (view === 'forgot') {
        // 비밀번호 찾기는 아직 DB 연동 없이 시뮬레이션 (메일 서버 필요하므로)
        alert(`[${formData.email}]로 재설정 링크를 보냈습니다.`);
        setView('login');
      }
    } catch (error) {
      console.error(error);
      alert("서버 연결에 실패했습니다.");
    }

    setIsLoading(false);
  };

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* 배경 효과 */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/20 rounded-full blur-[120px] animate-pulse"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/20 rounded-full blur-[120px] animate-pulse" style={{animationDelay: "2s"}}></div>
      </div>

      <div className="z-10 w-full max-w-md">
        {/* 로고 영역 */}
        <div className="flex justify-center items-center mb-10 select-none">
          <div className="relative flex items-center">
            <span className="text-[7rem] font-black bg-clip-text text-transparent bg-gradient-to-br from-blue-500 to-purple-600 leading-none mr-2">X</span>
            <div className="flex flex-col justify-center h-full space-y-[-10px]">
              <span className="text-4xl font-bold text-white tracking-widest">tock</span>
              <span className="text-4xl font-bold text-slate-400 tracking-widest">ignal</span>
            </div>
          </div>
        </div>

        {/* 폼 카드 */}
        <div className="bg-slate-900/50 border border-slate-800 backdrop-blur-xl rounded-3xl p-8 shadow-2xl">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-white">
              {view === 'login' && "Welcome Back"}
              {view === 'signup' && "Create Account"}
              {view === 'forgot' && "Reset Password"}
            </h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* 사용자 이름 (회원가입만) */}
            {view === 'signup' && (
              <div className="relative group">
                <User className="absolute left-4 top-3.5 w-5 h-5 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
                <input 
                  name="username"
                  type="text" 
                  required
                  placeholder="사용자 이름" 
                  value={formData.username}
                  onChange={handleChange}
                  className="w-full bg-black/40 border border-slate-700 rounded-xl py-3 pl-12 pr-4 text-white focus:border-blue-500 outline-none transition-all"
                />
              </div>
            )}

            {/* 이메일 (공통) */}
            <div className="relative group">
              <Mail className="absolute left-4 top-3.5 w-5 h-5 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
              <input 
                name="email"
                type="email" 
                required
                placeholder="이메일 주소" 
                value={formData.email}
                onChange={handleChange}
                className="w-full bg-black/40 border border-slate-700 rounded-xl py-3 pl-12 pr-4 text-white focus:border-blue-500 outline-none transition-all"
              />
            </div>

            {/* 비밀번호 (비번찾기 제외) */}
            {view !== 'forgot' && (
              <div className="relative group">
                <Lock className="absolute left-4 top-3.5 w-5 h-5 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
                <input 
                  name="password"
                  type="password" 
                  required
                  placeholder="비밀번호" 
                  value={formData.password}
                  onChange={handleChange}
                  className="w-full bg-black/40 border border-slate-700 rounded-xl py-3 pl-12 pr-4 text-white focus:border-blue-500 outline-none transition-all"
                />
              </div>
            )}

            <button 
              type="submit" 
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 text-white font-bold py-3.5 rounded-xl transition-all shadow-lg shadow-blue-900/20 disabled:opacity-50"
            >
              {isLoading ? "처리 중..." : (view === 'login' ? "로그인" : view === 'signup' ? "회원가입" : "전송")}
            </button>
          </form>

          {/* 하단 링크들 */}
          <div className="mt-6 text-center space-y-2">
            {view === 'login' && (
              <>
                <p className="text-slate-500 text-sm">
                  계정이 없으신가요? <button onClick={() => setView('signup')} className="text-blue-400 hover:underline">회원가입</button>
                </p>
              </>
            )}
            {view === 'signup' && (
              <p className="text-slate-500 text-sm">
                이미 계정이 있으신가요? <button onClick={() => setView('login')} className="text-blue-400 hover:underline">로그인</button>
              </p>
            )}
            {view === 'forgot' && (
              <button onClick={() => setView('login')} className="text-slate-400 text-sm">← 로그인으로 돌아가기</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}