"use client";
import { useState } from "react";
import { useTheme } from "../components/ThemeProvider"; // 경로 확인 필요 (보통 context나 components 폴더)
import api from "../utils/api";
import { User, Lock, Save, ShieldCheck, Moon, Sun, Bell } from 'lucide-react';

export default function SettingsSection({ user }) {
  const { theme, toggleTheme } = useTheme();
  
  // 비밀번호 변경 폼 상태 관리
  const [formData, setFormData] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: ""
  });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // 유효성 검사
    if (formData.newPassword !== formData.confirmPassword) {
      alert("새 비밀번호가 일치하지 않습니다.");
      return;
    }
    if (formData.newPassword.length < 4) {
      alert("비밀번호는 최소 4자 이상이어야 합니다.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/change-password", {
        email: user.email, // page.js에서 넘겨준 user 정보 사용
        current_password: formData.currentPassword,
        new_password: formData.newPassword
      });

      if (res.data.success) {
        alert("비밀번호가 변경되었습니다. 다음 로그인부터 적용됩니다.");
        setFormData({ currentPassword: "", newPassword: "", confirmPassword: "" });
      } else {
        alert(res.data.msg || "비밀번호 변경 실패");
      }
    } catch (error) {
      console.error(error);
      alert("서버 오류가 발생했습니다.");
    }
    setLoading(false);
  };

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl mx-auto pb-10">
      
      {/* 1. 프로필 정보 카드 (사용자 확인용) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex items-center gap-6 shadow-lg">
        <div className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-2xl font-bold text-white shadow-inner">
          {user?.username?.charAt(0).toUpperCase()}
        </div>
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            {user?.username}
            <span className="bg-blue-900/50 text-blue-400 text-xs px-2 py-0.5 rounded border border-blue-500/30">USER</span>
          </h2>
          <p className="text-slate-400 text-sm">{user?.email}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* 2. 일반 설정 (기존 기능 유지: 알림 + 테마) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 h-fit">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
            <SettingsIcon className="text-slate-400" /> 일반 설정
          </h3>
          
          <div className="space-y-1 divide-y divide-slate-800">
            {/* 알림 설정 */}
            <div className="flex items-center justify-between py-4">
              <div className="flex items-center gap-3">
                <Bell size={20} className="text-slate-400" />
                <span className="text-slate-200">알림 설정</span>
              </div>
              <button className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors">
                설정
              </button>
            </div>

            {/* 테마 변경 */}
            <div className="flex items-center justify-between py-4">
              <div className="flex items-center gap-3">
                {theme === 'dark' ? <Moon size={20} className="text-yellow-400" /> : <Sun size={20} className="text-orange-400" />}
                <span className="text-slate-200">테마 변경</span>
              </div>
              <button
                onClick={toggleTheme}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 transition-colors"
              >
                {theme === "dark" ? "라이트 모드" : "다크 모드"}
              </button>
            </div>
          </div>
        </div>

        {/* 3. 보안 설정 (비밀번호 변경 폼 추가) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h3 className="text-lg font-bold text-white mb-6 flex items-center gap-2">
            <Lock className="text-blue-500" size={20} /> 보안 설정
          </h3>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 ml-1">현재 비밀번호</label>
              <input 
                type="password"
                name="currentPassword"
                value={formData.currentPassword}
                onChange={handleChange}
                placeholder="현재 비밀번호 입력"
                className="w-full bg-black/30 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-slate-600"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 ml-1">새 비밀번호</label>
              <input 
                type="password"
                name="newPassword"
                value={formData.newPassword}
                onChange={handleChange}
                placeholder="변경할 비밀번호"
                className="w-full bg-black/30 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-slate-600"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-slate-400 ml-1">새 비밀번호 확인</label>
              <input 
                type="password"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="비밀번호 한 번 더 입력"
                className="w-full bg-black/30 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:ring-1 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all placeholder:text-slate-600"
                required
              />
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white py-3 rounded-xl font-bold text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? "변경 중..." : (
                <>
                  <Save size={16} /> 변경사항 저장
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

// 아이콘 컴포넌트 편의용
function SettingsIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.47a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.39a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}