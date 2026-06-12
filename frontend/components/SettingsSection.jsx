"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import api from "../utils/api";
import { useValuationPrices } from "../hooks/useValuationPrices";
import { computeSimulationMetrics } from "../utils/simulationPortfolio";

const formatMoney = (n) => {
  const num = Number(n);
  if (Number.isNaN(num)) return "$0.00";
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const inputClass =
  "w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2.5 text-white outline-none focus:ring-2 focus:ring-blue-500";

export default function SettingsSection({ user = null, onUserUpdate, onLogout }) {
  const email = user?.email?.trim();

  const [profileLoading, setProfileLoading] = useState(true);
  const [accountLoading, setAccountLoading] = useState(true);
  const [profile, setProfile] = useState(null);

  const [usernameInput, setUsernameInput] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);

  const [pinIsSet, setPinIsSet] = useState(false);
  const [oldPin, setOldPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [pinBusy, setPinBusy] = useState(false);

  const [deletePassword, setDeletePassword] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [cash, setCash] = useState(0);
  const [holdings, setHoldings] = useState({});
  const [trades, setTrades] = useState([]);
  const [simulationStarted, setSimulationStarted] = useState(false);

  const loadProfile = useCallback(async () => {
    if (!email) {
      setProfile(null);
      setProfileLoading(false);
      return;
    }
    setProfileLoading(true);
    try {
      const res = await api.post("/api/user/profile", { email });
      if (res?.data?.success && res.data.profile) {
        const p = res.data.profile;
        setProfile(p);
        setUsernameInput(p.username || "");
        setEmailInput(p.email || "");
        setPinIsSet(Boolean(p.pin_set));
      }
    } catch (e) {
      console.error("Failed to load user profile", e);
    } finally {
      setProfileLoading(false);
    }
  }, [email]);

  const loadSimulationAccount = useCallback(async () => {
    if (!email) {
      setCash(0);
      setHoldings({});
      setTrades([]);
      setSimulationStarted(false);
      setAccountLoading(false);
      return;
    }
    setAccountLoading(true);
    try {
      const res = await api.post("/api/simulation/state/get", { email });
      const state = res?.data?.state;
      if (res?.data?.success && res?.data?.exists && state) {
        setCash(Number(state.cash) || 0);
        setHoldings(state.holdings || {});
        setTrades(Array.isArray(state.trades) ? state.trades : []);
        setSimulationStarted(Boolean(state.simulation_started));
      } else {
        setCash(0);
        setHoldings({});
        setTrades([]);
        setSimulationStarted(false);
      }
    } catch (e) {
      console.error("Failed to load simulation account", e);
    } finally {
      setAccountLoading(false);
    }
  }, [email]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadProfile();
      void loadSimulationAccount();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadProfile, loadSimulationAccount]);

  const { getValuationPrice } = useValuationPrices(holdings, simulationStarted);
  const { totalValue, totalPnl, holdingList } = useMemo(
    () => computeSimulationMetrics(cash, holdings, getValuationPrice),
    [cash, holdings, getValuationPrice]
  );

  const saveProfile = async () => {
    if (!email) return;
    const pwd = currentPassword.trim();
    if (!pwd) {
      alert("변경을 위해 현재 비밀번호를 입력해주세요.");
      return;
    }

    const nextUsername = usernameInput.trim();
    const nextEmail = emailInput.trim();
    const nextPwd = newPassword.trim();

    if (nextPwd && nextPwd !== confirmPassword.trim()) {
      alert("새 비밀번호 확인이 일치하지 않습니다.");
      return;
    }

    const body = {
      email,
      current_password: pwd,
    };
    if (nextUsername && nextUsername !== profile?.username) {
      body.username = nextUsername;
    }
    if (nextEmail && nextEmail.toLowerCase() !== (profile?.email || email).toLowerCase()) {
      body.new_email = nextEmail;
    }
    if (nextPwd) {
      body.new_password = nextPwd;
    }

    if (!body.username && !body.new_email && !body.new_password) {
      alert("변경할 항목을 입력해주세요.");
      return;
    }

    setProfileBusy(true);
    try {
      const res = await api.post("/api/user/update", body);
      if (res?.data?.success) {
        const updated = res.data.user;
        if (updated && onUserUpdate) {
          onUserUpdate(updated);
        }
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        alert(res.data.msg || "저장되었습니다.");
        if (updated?.email && updated.email !== email) {
          await loadSimulationAccount();
        }
        await loadProfile();
      } else {
        alert(res?.data?.msg || "저장에 실패했습니다.");
      }
    } catch (e) {
      console.error(e);
      alert("서버 오류로 저장하지 못했습니다.");
    } finally {
      setProfileBusy(false);
    }
  };

  const savePin = async () => {
    const activeEmail = (profile?.email || email || "").trim();
    if (!activeEmail) return;
    if (!/^\d{4}$/.test(newPin)) {
      alert("PIN은 4자리 숫자여야 합니다.");
      return;
    }
    if (newPin !== confirmPin) {
      alert("PIN 확인이 일치하지 않습니다.");
      return;
    }
    if (pinIsSet && !/^\d{4}$/.test(oldPin)) {
      alert("기존 PIN 4자리를 입력해주세요.");
      return;
    }

    setPinBusy(true);
    try {
      const body = pinIsSet
        ? { email: activeEmail, pin: newPin, old_pin: oldPin }
        : { email: activeEmail, pin: newPin };
      const res = await api.post("/api/simulation/pin/set", body);
      if (res?.data?.success) {
        setPinIsSet(true);
        setOldPin("");
        setNewPin("");
        setConfirmPin("");
        alert(res.data.msg || "PIN이 저장되었습니다.");
        await loadProfile();
      } else {
        alert(res?.data?.msg || "PIN 저장에 실패했습니다.");
      }
    } catch (e) {
      console.error(e);
      alert("서버 오류로 PIN을 저장하지 못했습니다.");
    } finally {
      setPinBusy(false);
    }
  };

  const deleteAccount = async () => {
    const activeEmail = (profile?.email || email || "").trim();
    if (!activeEmail) return;

    const pwd = deletePassword.trim();
    if (!pwd) {
      alert("탈퇴를 위해 비밀번호를 입력해주세요.");
      return;
    }

    const confirmed = window.confirm(
      "정말 회원탈퇴하시겠습니까?\n\n계정과 시뮬레이션 데이터가 모두 삭제되며 복구할 수 없습니다."
    );
    if (!confirmed) return;

    setDeleteBusy(true);
    try {
      const res = await api.post("/api/user/delete", {
        email: activeEmail,
        current_password: pwd,
      });
      if (res?.data?.success) {
        alert(res.data.msg || "회원탈퇴가 완료되었습니다.");
        setDeletePassword("");
        if (onLogout) onLogout();
      } else {
        alert(res?.data?.msg || "회원탈퇴에 실패했습니다.");
      }
    } catch (e) {
      console.error(e);
      alert("서버 오류로 탈퇴 처리하지 못했습니다.");
    } finally {
      setDeleteBusy(false);
    }
  };

  if (!email) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
        <p className="text-slate-400 text-sm">로그인 후 설정을 변경할 수 있습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-8">

      {/* 시뮬레이션 계좌 */}
      <section className="bg-slate-800/30 border border-slate-700 rounded-2xl p-5 space-y-4">
        <h3 className="text-white font-semibold">시뮬레이션 계좌</h3>
        {accountLoading ? (
          <p className="text-slate-400 text-sm">계좌 정보를 불러오는 중</p>
        ) : !simulationStarted ? (
          <p className="text-slate-400 text-sm">
            아직 시작한 시뮬레이션 계좌가 없습니다. 주식 시뮬레이션에서 계좌를 시작하세요.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">가상 현금</div>
              <div className="text-white text-lg font-bold">{formatMoney(cash)}</div>
            </div>
            <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">계좌 총액</div>
              <div className="text-white text-lg font-bold">{formatMoney(totalValue)}</div>
            </div>
            <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">총 손익</div>
              <div
                className={`text-lg font-bold ${
                  totalPnl >= 0 ? "text-green-400" : "text-red-400"
                }`}
              >
                {totalPnl >= 0 ? "+" : "-"}
                {formatMoney(Math.abs(totalPnl))}
              </div>
            </div>
            <div className="bg-slate-900/50 border border-slate-700 rounded-xl p-4">
              <div className="text-slate-400 text-xs mb-1">보유 / 거래</div>
              <div className="text-white text-lg font-bold">
                {holdingList.length}종목 / {trades.length}건
              </div>
            </div>
          </div>
        )}
      </section>

      {/* 사용자명 / 이메일 / 비밀번호 */}
      <section className="bg-slate-800/30 border border-slate-700 rounded-2xl p-5 space-y-4">
        <h3 className="text-white font-semibold">프로필 변경</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-xs mb-1">사용자명</label>
            <input
              type="text"
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              className={inputClass}
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-xs mb-1">이메일</label>
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              className={inputClass}
              autoComplete="email"
            />
          </div>
        </div>

        <div>
          <label className="block text-slate-300 text-xs mb-1">현재 비밀번호</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className={inputClass}
            autoComplete="current-password"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-slate-300 text-xs mb-1">새 비밀번호</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClass}
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="block text-slate-300 text-xs mb-1">새 비밀번호 확인</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={inputClass}
              autoComplete="new-password"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={() => void saveProfile()}
          disabled={profileBusy || profileLoading}
          className="px-5 py-2.5 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
        >
          {profileBusy ? "저장 중" : "프로필 저장"}
        </button>
      </section>

      {/* PIN */}
      <section className="bg-slate-800/30 border border-slate-700 rounded-2xl p-5 space-y-4">
        <h3 className="text-white font-semibold">거래 PIN 변경</h3>
        {pinIsSet ? (
          <div>
            <label className="block text-slate-300 text-xs mb-1">기존 PIN</label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={oldPin}
              onChange={(e) => setOldPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
              className={`${inputClass} max-w-[11rem] tracking-widest`}
              autoComplete="off"
            />
          </div>
        ) : null}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
          <div>
            <label className="block text-slate-300 text-xs mb-1">
              {pinIsSet ? "새 PIN" : "PIN 설정"}
            </label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={newPin}
              onChange={(e) => setNewPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
              className={`${inputClass} tracking-widest`}
            />
          </div>
          <div>
            <label className="block text-slate-300 text-xs mb-1">PIN 확인</label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={4}
              value={confirmPin}
              onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
              className={`${inputClass} tracking-widest`}
            />
          </div>
        </div>

        <button
          type="button"
          onClick={() => void savePin()}
          disabled={pinBusy || newPin.length !== 4 || confirmPin.length !== 4}
          className="px-5 py-2.5 rounded-lg font-semibold bg-blue-600 hover:bg-blue-500 text-white text-sm disabled:opacity-50"
        >
          {pinBusy ? "저장 중" : pinIsSet ? "PIN 변경" : "PIN 설정"}
        </button>
      </section>

      {/* 프로필 표시 */}
      <section className="bg-slate-800/30 border border-slate-700 rounded-2xl p-5 space-y-3">
        <h3 className="text-white font-semibold">내 정보</h3>
        {profileLoading ? (
          <p className="text-slate-400 text-sm">불러오는 중</p>
        ) : (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg px-3 py-2">
              <dt className="text-slate-500 text-xs">가입일</dt>
              <dd className="text-slate-200 mt-0.5">{profile?.created_at || "—"}</dd>
            </div>
            <div className="bg-slate-900/40 border border-slate-700 rounded-lg px-3 py-2">
              <dt className="text-slate-500 text-xs">거래 PIN</dt>
              <dd className="text-slate-200 mt-0.5">
                {pinIsSet
                  ? `설정됨${profile?.simulation_pin_set_at ? ` (${profile.simulation_pin_set_at.slice(0, 10)})` : ""}`
                  : "미설정"}
              </dd>
            </div>
          </dl>
        )}
      </section>

      {/* 회원탈퇴 */}
      <section className="bg-red-950/20 border border-red-900/50 rounded-2xl p-5 space-y-4">
        <h3 className="text-red-300 font-semibold">회원탈퇴</h3>
        <p className="text-slate-400 text-sm leading-relaxed">
          탈퇴 시 users 계정과 시뮬레이션 계좌·거래 내역이 모두 삭제되며 되돌릴 수 없습니다.
        </p>
        <div className="max-w-md">
          <label className="block text-slate-300 text-xs mb-1">비밀번호 확인</label>
          <input
            type="password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            className={inputClass}
            autoComplete="current-password"
            placeholder="현재 비밀번호"
          />
        </div>
        <button
          type="button"
          onClick={() => void deleteAccount()}
          disabled={deleteBusy || !deletePassword.trim()}
          className="px-5 py-2.5 rounded-lg font-semibold bg-red-700 hover:bg-red-600 text-white text-sm disabled:opacity-50"
        >
          {deleteBusy ? "처리 중…" : "회원탈퇴"}
        </button>
      </section>
    </div>
  );
}
