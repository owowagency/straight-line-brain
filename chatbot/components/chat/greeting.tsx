import { motion } from "framer-motion";
import { SLLLogo } from "./icons";

export const Greeting = () => {
  return (
    <div className="flex flex-col items-center px-4" key="overview">
      {/* Logo with gold glow halo */}
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="relative mb-8"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.2, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -inset-x-16 -inset-y-8"
          style={{
            background:
              "radial-gradient(ellipse at center, oklch(0.72 0.12 80 / 0.08) 0%, transparent 70%)",
          }}
        />
        <SLLLogo className="relative text-primary" size={500} />
      </motion.div>

      {/* Parallelogram divider */}
      <motion.div
        animate={{ opacity: 1, scaleX: 1 }}
        className="mb-6 h-[2px] w-12 skew-sll bg-primary/40"
        initial={{ opacity: 0, scaleX: 0 }}
        transition={{ delay: 0.4, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      />

      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="text-center font-semibold text-2xl tracking-tight text-foreground md:text-3xl"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.5, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        Straight-Line Leadership
      </motion.div>
      <motion.div
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 text-center text-muted-foreground text-sm"
        initial={{ opacity: 0, y: 10 }}
        transition={{ delay: 0.65, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        Ask about the methodology, distinctions, or coaching programs.
      </motion.div>
    </div>
  );
};
