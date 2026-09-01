import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Logo } from "@/components/Brand";
import { ArrowLeft, Mail, KeyRound, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";

export default function ForgotPassword() {
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [loading, setLoading] = useState(false);

  const requestOtp = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      toast.success("If the account exists, an OTP has been emailed to you.");
      setStep(2);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    if (otp.length !== 6) {
      toast.error("Enter the 6-digit OTP");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", { email, otp });
      toast.success("OTP verified. Choose a new password.");
      setStep(3);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const resetPass = async (e) => {
    e.preventDefault();
    if (newPass.length < 6) return toast.error("Password must be 6+ characters");
    if (newPass !== confirmPass) return toast.error("Passwords do not match");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { email, otp, new_password: newPass });
      toast.success("Password updated. Please sign in.");
      nav("/login");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { n: 1, t: "Email", Icon: Mail },
    { n: 2, t: "Verify OTP", Icon: KeyRound },
    { n: 3, t: "New Password", Icon: ShieldCheck },
  ];

  return (
    <div className="min-h-screen bg-mesh grain flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        <Link to="/login" className="text-sm text-slate-400 hover:text-orange-400 flex items-center gap-1 mb-8" data-testid="back-to-login">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
        <div className="mb-8"><Logo /></div>

        <div className="flex items-center gap-3 mb-10">
          {steps.map((s, i) => (
            <div key={s.n} className="flex items-center gap-3 flex-1">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all ${step >= s.n ? "border-orange-500 bg-orange-500/20 text-orange-400" : "border-white/10 text-slate-500"}`}>
                <s.Icon size={16} />
              </div>
              <div className="hidden sm:block">
                <div className={`text-[10px] font-mono uppercase tracking-widest ${step >= s.n ? "text-orange-400" : "text-slate-500"}`}>Step {s.n}</div>
                <div className={`text-sm font-semibold ${step >= s.n ? "text-white" : "text-slate-500"}`}>{s.t}</div>
              </div>
              {i < steps.length - 1 && <div className={`h-px flex-1 ${step > s.n ? "bg-orange-500" : "bg-white/10"}`} />}
            </div>
          ))}
        </div>

        <div className="card p-8">
          {step === 1 && (
            <form onSubmit={requestOtp} className="space-y-5" data-testid="fp-step-1">
              <h1 className="font-display text-3xl font-black">Reset your password</h1>
              <p className="text-slate-400 text-sm">Enter your registered email — we'll send a 6-digit OTP.</p>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Email</label>
                <input type="email" className="input-field" placeholder="you@bandish.club" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="fp-email-input" />
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full" data-testid="fp-send-otp-btn">{loading ? "Sending..." : "Send OTP"}</button>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={verifyOtp} className="space-y-5" data-testid="fp-step-2">
              <h1 className="font-display text-3xl font-black">Enter OTP</h1>
              <p className="text-slate-400 text-sm">We sent a 6-digit code to <span className="text-orange-400 font-semibold">{email}</span>. It expires in 10 minutes.</p>
              <div className="flex justify-center py-2">
                <InputOTP maxLength={6} value={otp} onChange={setOtp} data-testid="fp-otp-input">
                  <InputOTPGroup>
                    {[0, 1, 2, 3, 4, 5].map((i) => <InputOTPSlot key={i} index={i} className="w-12 h-14 text-xl border-white/10 bg-black/40" />)}
                  </InputOTPGroup>
                </InputOTP>
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full" data-testid="fp-verify-otp-btn">{loading ? "Verifying..." : "Verify OTP"}</button>
              <button type="button" onClick={() => setStep(1)} className="text-sm text-slate-400 hover:text-orange-400 w-full text-center" data-testid="fp-back-to-email">Resend OTP / Change Email</button>
            </form>
          )}

          {step === 3 && (
            <form onSubmit={resetPass} className="space-y-5" data-testid="fp-step-3">
              <h1 className="font-display text-3xl font-black">New password</h1>
              <p className="text-slate-400 text-sm">Pick something strong. At least 6 characters.</p>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">New Password</label>
                <input type="password" className="input-field" placeholder="••••••••" value={newPass} onChange={(e) => setNewPass(e.target.value)} required data-testid="fp-new-password-input" />
              </div>
              <div>
                <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Confirm Password</label>
                <input type="password" className="input-field" placeholder="••••••••" value={confirmPass} onChange={(e) => setConfirmPass(e.target.value)} required data-testid="fp-confirm-password-input" />
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full" data-testid="fp-reset-submit-btn">{loading ? "Updating..." : "Update Password"}</button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
