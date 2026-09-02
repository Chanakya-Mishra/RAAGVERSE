import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Logo } from "@/components/Brand";
import { ArrowLeft, Mail, KeyRound, ShieldCheck, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";

export default function ForgotPassword() {
  const nav = useNavigate();
  const [channel, setChannel] = useState("email"); // 'email' | 'sms'
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [loading, setLoading] = useState(false);

  const identifierBody = () => (channel === "sms" ? { phone } : { email });
  const readableIdentifier = channel === "sms" ? phone : email;

  const requestOtp = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const path = channel === "sms" ? "/auth/forgot-password-sms" : "/auth/forgot-password";
      const { data } = await api.post(path, identifierBody());
      if (data.delivered === false) {
        toast.warning("Code generated but delivery failed. Ask an admin (Chanakya or Siddharth) for your code.", { duration: 8000 });
      } else {
        toast.success(channel === "sms" ? "SMS sent — check your phone." : "If the account exists, a code was emailed.");
      }
      setStep(2);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  const verifyOtp = async (e) => {
    e.preventDefault();
    if (otp.length !== 6) return toast.error("Enter the 6-digit code");
    setLoading(true);
    try {
      await api.post("/auth/verify-otp", { ...identifierBody(), otp });
      toast.success("Code verified. Set a new password.");
      setStep(3);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  const resetPass = async (e) => {
    e.preventDefault();
    if (newPass.length < 6) return toast.error("Password must be 6+ characters");
    if (newPass !== confirmPass) return toast.error("Passwords do not match");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { ...identifierBody(), otp, new_password: newPass });
      toast.success("Password updated. Please sign in.");
      nav("/login");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally { setLoading(false); }
  };

  const steps = [
    { n: 1, t: channel === "sms" ? "Phone" : "Email", Icon: channel === "sms" ? MessageSquare : Mail },
    { n: 2, t: "Verify Code", Icon: KeyRound },
    { n: 3, t: "New Password", Icon: ShieldCheck },
  ];

  return (
    <div className="min-h-screen bg-mesh grain flex items-center justify-center p-6">
      <div className="w-full max-w-xl">
        <Link to="/login" className="text-sm text-slate-400 hover:text-orange-400 flex items-center gap-1 mb-8" data-testid="back-to-login">
          <ArrowLeft size={14} /> Back to sign in
        </Link>
        <div className="mb-8"><Logo /></div>

        <div className="flex items-center gap-3 mb-6">
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
            <>
              <div className="flex gap-2 mb-6 border border-white/10 rounded-full p-1 max-w-xs" data-testid="fp-channel-toggle">
                {[
                  { id: "email", label: "Email", Icon: Mail },
                  { id: "sms", label: "SMS", Icon: MessageSquare },
                ].map((c) => (
                  <button key={c.id} type="button" onClick={() => setChannel(c.id)}
                    className={`flex-1 text-sm py-1.5 rounded-full transition flex items-center justify-center gap-2 ${channel === c.id ? "bg-gradient-to-r from-orange-500 to-red-500 text-white" : "text-slate-300 hover:text-white"}`}
                    data-testid={`fp-channel-${c.id}`}
                  >
                    <c.Icon size={14} /> {c.label}
                  </button>
                ))}
              </div>

              <form onSubmit={requestOtp} className="space-y-5" data-testid="fp-step-1">
                <h1 className="font-display text-3xl font-black">Reset your password</h1>
                <p className="text-slate-400 text-sm">
                  {channel === "sms"
                    ? "Enter your registered phone number — we'll text you a 6-digit code."
                    : "Enter your registered email — we'll email you a 6-digit code."}
                </p>
                {channel === "sms" ? (
                  <div>
                    <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Phone (E.164)</label>
                    <input type="tel" className="input-field" placeholder="+14155552671" value={phone} onChange={(e) => setPhone(e.target.value)} required data-testid="fp-phone-input" />
                    <div className="text-[11px] text-slate-500 mt-1">Include the country code with a leading +</div>
                  </div>
                ) : (
                  <div>
                    <label className="text-xs font-mono uppercase tracking-widest text-slate-400 mb-2 block">Email</label>
                    <input type="email" className="input-field" placeholder="you@bandish.club" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="fp-email-input" />
                  </div>
                )}
                <button type="submit" disabled={loading} className="btn-primary w-full" data-testid="fp-send-otp-btn">{loading ? "Sending..." : (channel === "sms" ? "Send SMS Code" : "Send Email Code")}</button>
              </form>
            </>
          )}

          {step === 2 && (
            <form onSubmit={verifyOtp} className="space-y-5" data-testid="fp-step-2">
              <h1 className="font-display text-3xl font-black">Enter code</h1>
              <p className="text-slate-400 text-sm">
                We sent a 6-digit code to <span className="text-orange-400 font-semibold">{readableIdentifier}</span>. It expires in 10 minutes.
              </p>
              <div className="flex justify-center py-2">
                <InputOTP maxLength={6} value={otp} onChange={setOtp} data-testid="fp-otp-input">
                  <InputOTPGroup>
                    {[0, 1, 2, 3, 4, 5].map((i) => <InputOTPSlot key={i} index={i} className="w-12 h-14 text-xl border-white/10 bg-black/40" />)}
                  </InputOTPGroup>
                </InputOTP>
              </div>
              <button type="submit" disabled={loading} className="btn-primary w-full" data-testid="fp-verify-otp-btn">{loading ? "Verifying..." : "Verify Code"}</button>
              <button type="button" onClick={() => setStep(1)} className="text-sm text-slate-400 hover:text-orange-400 w-full text-center" data-testid="fp-back-to-email">Resend / Change Identifier</button>
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
