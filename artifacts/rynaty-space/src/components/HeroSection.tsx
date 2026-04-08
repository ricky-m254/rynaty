import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { assetUrl } from "@/lib/assets";

function Starfield() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const stars: { x: number; y: number; r: number; a: number; speed: number }[] = [];
    for (let i = 0; i < 200; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.5 + 0.3,
        a: Math.random(),
        speed: Math.random() * 0.005 + 0.002,
      });
    }

    let animId: number;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const s of stars) {
        s.a += s.speed;
        if (s.a > 1) s.a = 0;
        const alpha = Math.abs(Math.sin(s.a * Math.PI));
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha * 0.8})`;
        ctx.fill();
      }
      animId = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none"
    />
  );
}

export default function HeroSection() {
  const scrollToProducts = () => {
    document.getElementById("products")?.scrollIntoView({ behavior: "smooth" });
  };
  const scrollToContact = () => {
    document.getElementById("contact")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section
      id="hero"
      className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden"
    >
      <div className="absolute inset-0 bg-[#0d1117]" />
      <div className="absolute inset-0 bg-gradient-to-br from-[#0d1117] via-[#0a1628] to-[#0d1117]" />
      <div
        className="absolute inset-0 opacity-30"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(34,197,94,0.12) 0%, transparent 70%)",
        }}
      />

      <Starfield />

      <div className="relative z-10 text-center px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="mb-8 flex justify-center"
        >
          <img
            src={assetUrl("assets/rsp-logo.png")}
            alt="Rynaty Space Technologies"
            className="h-28 sm:h-36 lg:h-44 w-auto"
            style={{ filter: "drop-shadow(0 0 30px rgba(34,197,94,0.5)) brightness(1.05)" }}
          />
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="text-3xl sm:text-4xl lg:text-6xl font-extrabold text-white mb-4 tracking-tight"
        >
          Powering Africa's{" "}
          <span
            style={{
              background: "linear-gradient(135deg, #22c55e 0%, #4ade80 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Digital Future
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.5 }}
          className="text-base sm:text-lg lg:text-xl text-slate-300 mb-10 max-w-2xl mx-auto leading-relaxed"
        >
          Smart campus solutions, cloud platforms, and digital tools transforming
          education and business across Africa. Built for tomorrow's leaders.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.7 }}
          className="flex flex-col sm:flex-row gap-4 justify-center"
        >
          <button
            onClick={scrollToProducts}
            className="inline-flex items-center justify-center gap-2 bg-[#22c55e] hover:bg-[#16a34a] text-black font-bold text-base px-8 py-3.5 rounded-xl transition-all duration-200 shadow-lg hover:shadow-green-500/30 hover:scale-105"
          >
            View Products
          </button>
          <button
            onClick={scrollToContact}
            className="inline-flex items-center justify-center gap-2 border border-[#22c55e] text-[#22c55e] hover:bg-[#22c55e]/10 font-bold text-base px-8 py-3.5 rounded-xl transition-all duration-200 hover:scale-105"
          >
            Contact Us
          </button>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 1 }}
        className="absolute bottom-8 left-1/2 -translate-x-1/2 text-slate-500"
      >
        <ChevronDown
          size={28}
          className="animate-bounce cursor-pointer hover:text-[#22c55e] transition-colors"
          onClick={scrollToProducts}
        />
      </motion.div>
    </section>
  );
}
