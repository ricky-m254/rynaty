import { useState } from "react";
import { Phone, Mail, Send, MapPin } from "lucide-react";
import { toast } from "sonner";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";

export default function ContactSection() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.message.trim()) {
      toast.error("Please fill in all fields.");
      return;
    }
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      setSubmitted(true);
      setForm({ name: "", email: "", message: "" });
      toast.success("Enquiry received! We'll get back to you shortly.", {
        duration: 8000,
      });
      setTimeout(() => setSubmitted(false), 6000);
    }, 800);
  };

  return (
    <section
      id="contact"
      className="py-20 px-4 sm:px-6 lg:px-8"
      style={{ background: "linear-gradient(180deg, #0d1117 0%, #091218 100%)" }}
    >
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Get In Touch"
            title="Ready to Transform"
            highlight="Your School?"
            subtitle="Contact us today to discuss how Rynaty Space Technologies can help digitise your institution."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-10 max-w-5xl mx-auto">
          <AnimatedSection className="lg:col-span-2" delay={0.1}>
            <div className="h-full flex flex-col gap-6">
              <div className="p-6 rounded-xl border border-[#1e2d3d] bg-[#0f1823]">
                <h3 className="text-white font-bold text-lg mb-6">Contact Details</h3>
                <div className="flex flex-col gap-5">
                  <a
                    href="tel:0707032911"
                    className="flex items-center gap-4 group"
                  >
                    <div className="w-11 h-11 rounded-xl bg-[#22c55e]/10 border border-[#22c55e]/25 flex items-center justify-center flex-shrink-0">
                      <Phone size={18} className="text-[#22c55e]" />
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs mb-0.5">Phone</p>
                      <p className="text-white font-medium text-sm group-hover:text-[#22c55e] transition-colors">
                        0707032911
                      </p>
                    </div>
                  </a>
                  <a
                    href="mailto:emurithi593@gmail.com"
                    className="flex items-center gap-4 group"
                  >
                    <div className="w-11 h-11 rounded-xl bg-[#22c55e]/10 border border-[#22c55e]/25 flex items-center justify-center flex-shrink-0">
                      <Mail size={18} className="text-[#22c55e]" />
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs mb-0.5">Email</p>
                      <p className="text-white font-medium text-sm group-hover:text-[#22c55e] transition-colors break-all">
                        emurithi593@gmail.com
                      </p>
                    </div>
                  </a>
                  <div className="flex items-center gap-4">
                    <div className="w-11 h-11 rounded-xl bg-[#22c55e]/10 border border-[#22c55e]/25 flex items-center justify-center flex-shrink-0">
                      <MapPin size={18} className="text-[#22c55e]" />
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs mb-0.5">Location</p>
                      <p className="text-white font-medium text-sm">Africa</p>
                    </div>
                  </div>
                </div>
              </div>

              <div
                className="p-6 rounded-xl border border-[#22c55e]/25 flex-1"
                style={{ background: "linear-gradient(135deg, rgba(34,197,94,0.08) 0%, rgba(34,197,94,0.03) 100%)" }}
              >
                <p className="text-slate-300 text-sm leading-relaxed">
                  We're here to help you digitise and modernise your school or business.
                  Reach out and our team will respond within 24 hours.
                </p>
                <div className="mt-4 flex items-center gap-2">
                  <span className="w-2 h-2 bg-[#22c55e] rounded-full animate-pulse" />
                  <span className="text-[#22c55e] text-xs font-medium">Available for new projects</span>
                </div>
              </div>
            </div>
          </AnimatedSection>

          <AnimatedSection className="lg:col-span-3" delay={0.2}>
            <form
              onSubmit={handleSubmit}
              className="p-6 sm:p-8 rounded-xl border border-[#1e2d3d] bg-[#0f1823] h-full flex flex-col"
            >
              <h3 className="text-white font-bold text-lg mb-6">Send an Enquiry</h3>
              <div className="flex flex-col gap-4 flex-1">
                <div>
                  <label className="text-slate-400 text-xs font-medium mb-1.5 block">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Your full name"
                    className="w-full bg-[#0d1117] border border-[#1e2d3d] rounded-lg px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#22c55e] focus:ring-1 focus:ring-[#22c55e]/30 transition-all"
                  />
                </div>
                <div>
                  <label className="text-slate-400 text-xs font-medium mb-1.5 block">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="your@email.com"
                    className="w-full bg-[#0d1117] border border-[#1e2d3d] rounded-lg px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#22c55e] focus:ring-1 focus:ring-[#22c55e]/30 transition-all"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-slate-400 text-xs font-medium mb-1.5 block">
                    Message
                  </label>
                  <textarea
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    placeholder="Tell us about your school or project..."
                    rows={5}
                    className="w-full bg-[#0d1117] border border-[#1e2d3d] rounded-lg px-4 py-3 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-[#22c55e] focus:ring-1 focus:ring-[#22c55e]/30 transition-all resize-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full flex items-center justify-center gap-2 bg-[#22c55e] hover:bg-[#16a34a] disabled:opacity-60 disabled:cursor-not-allowed text-black font-bold text-sm px-6 py-3.5 rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-green-500/25 mt-2"
                >
                  {submitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send size={16} />
                      Send Enquiry
                    </>
                  )}
                </button>
                {submitted && (
                  <div
                    role="status"
                    aria-live="polite"
                    className="mt-3 p-3 rounded-lg border border-[#22c55e]/40 bg-[#22c55e]/10 text-[#22c55e] text-sm font-medium text-center"
                  >
                    Enquiry received! We'll get back to you shortly.
                  </div>
                )}
              </div>
            </form>
          </AnimatedSection>
        </div>
      </div>
    </section>
  );
}
