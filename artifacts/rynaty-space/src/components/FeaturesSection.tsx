import { Users, DollarSign, Fingerprint, MessageSquare, Library, Briefcase, Cloud } from "lucide-react";
import SectionTitle from "./SectionTitle";
import AnimatedSection from "./AnimatedSection";

const features = [
  {
    icon: Users,
    title: "Student Information & Admissions",
    description: "Complete student profiles, enrollment tracking, class assignments and admissions workflow management.",
    color: "#22c55e",
  },
  {
    icon: DollarSign,
    title: "Finance & Fee Tracking",
    description: "Automated fee collection, payment reminders, receipts, and detailed financial reporting dashboards.",
    color: "#4ade80",
  },
  {
    icon: Fingerprint,
    title: "Biometric Attendance (ZKTeco)",
    description: "Fingerprint-based attendance capture integrated with ZKTeco devices for accurate, real-time records.",
    color: "#22c55e",
  },
  {
    icon: MessageSquare,
    title: "SMS Notifications",
    description: "Instant SMS alerts to parents and staff for attendance, fees, results, and important school events.",
    color: "#4ade80",
  },
  {
    icon: Library,
    title: "Library Management",
    description: "Digital catalogue, book borrowing and returns, fine tracking and library resource management.",
    color: "#22c55e",
  },
  {
    icon: Briefcase,
    title: "Staff & Payroll",
    description: "Complete staff management, leave tracking, payslip generation, and payroll processing automation.",
    color: "#4ade80",
  },
  {
    icon: Cloud,
    title: "Cloud & Offline Support",
    description: "Works seamlessly online and offline — data syncs automatically when connectivity is restored.",
    color: "#22c55e",
  },
];

export default function FeaturesSection() {
  return (
    <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 bg-[#0d1117]">
      <div className="max-w-7xl mx-auto">
        <AnimatedSection>
          <SectionTitle
            label="Key Features"
            title="Everything You Need,"
            highlight="All in One Place"
            subtitle="Comprehensive tools that cover every aspect of school administration and operations."
          />
        </AnimatedSection>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {features.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <AnimatedSection key={feature.title} delay={i * 0.07}>
                <div className="p-5 rounded-xl border border-[#1e2d3d] bg-[#0f1823] hover:border-[#22c55e]/40 transition-all duration-300 hover:shadow-lg hover:shadow-green-500/10 group h-full">
                  <div
                    className="w-11 h-11 rounded-lg flex items-center justify-center mb-4"
                    style={{ background: `${feature.color}18`, border: `1px solid ${feature.color}30` }}
                  >
                    <Icon size={20} style={{ color: feature.color }} />
                  </div>
                  <h3 className="text-white font-semibold text-sm mb-2 group-hover:text-[#22c55e] transition-colors">
                    {feature.title}
                  </h3>
                  <p className="text-slate-400 text-xs leading-relaxed">{feature.description}</p>
                </div>
              </AnimatedSection>
            );
          })}
        </div>
      </div>
    </section>
  );
}
