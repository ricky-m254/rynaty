import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import { assetUrl } from "@/lib/assets";

const navLinks = [
  { label: "Products", href: "#products" },
  { label: "Features", href: "#features" },
  { label: "Hardware", href: "#hardware" },
  { label: "Cloud", href: "#cloud" },
  { label: "Services", href: "#services" },
  { label: "Vision", href: "#vision" },
];

interface NavbarProps {
  activeSection: string;
}

export default function Navbar({ activeSection }: NavbarProps) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler);
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const scrollTo = (href: string) => {
    setMenuOpen(false);
    const id = href.replace("#", "");
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-[#0d1117]/95 backdrop-blur-md border-b border-[#1e2d3d] shadow-lg"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 lg:h-20">
          <button
            onClick={() => scrollTo("#hero")}
            className="flex items-center gap-3 flex-shrink-0"
          >
            <img
              src={assetUrl("assets/rsp-logo.png")}
              alt="Rynaty Space Technologies"
              className="h-10 lg:h-12 w-auto"
            />
          </button>

          <div className="hidden lg:flex items-center gap-8">
            {navLinks.map((link) => {
              const sectionId = link.href.replace("#", "");
              const isActive = activeSection === sectionId;
              return (
                <button
                  key={link.href}
                  onClick={() => scrollTo(link.href)}
                  className={`text-sm font-medium transition-colors duration-200 relative pb-0.5 ${
                    isActive
                      ? "text-[#22c55e]"
                      : "text-slate-300 hover:text-white"
                  }`}
                >
                  {link.label}
                  {isActive && (
                    <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#22c55e] rounded-full" />
                  )}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => scrollTo("#contact")}
              className="hidden lg:inline-flex items-center gap-2 bg-[#22c55e] hover:bg-[#16a34a] text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-green-500/25"
            >
              Contact Us
            </button>
            <button
              className="lg:hidden text-slate-300 hover:text-white transition-colors"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
            >
              {menuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </div>

      {menuOpen && (
        <div className="lg:hidden bg-[#0d1117]/98 backdrop-blur-md border-t border-[#1e2d3d]">
          <div className="px-4 py-4 flex flex-col gap-2">
            {navLinks.map((link) => (
              <button
                key={link.href}
                onClick={() => scrollTo(link.href)}
                className="text-left text-slate-300 hover:text-[#22c55e] font-medium py-2.5 px-3 rounded-lg hover:bg-white/5 transition-all text-sm"
              >
                {link.label}
              </button>
            ))}
            <button
              onClick={() => scrollTo("#contact")}
              className="mt-2 w-full bg-[#22c55e] hover:bg-[#16a34a] text-black font-semibold text-sm px-5 py-2.5 rounded-lg transition-all"
            >
              Contact Us
            </button>
          </div>
        </div>
      )}
    </nav>
  );
}
