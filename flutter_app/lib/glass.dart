// FILE: glass.dart - NEW (v6) design tokens + small widgets for the "Oceanic Liquid Glass" Stitch design.
// Names start with "g" so they never clash with the older tokens in main.dart (which answer_card.dart still uses).
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ===== SECTION 1: colours from oceanic_liquid_glass/DESIGN.md =====
const gBg = Color(0xFF0C1420);
const gLow = Color(0xFF151C28);
const gCard = Color(0xFF19202C);
const gCardHigh = Color(0xFF232A37);
const gCyan = Color(0xFF00E5FF); // primary-container
const gSky = Color(0xFF4CD6FB); // secondary
const gIndigo = Color(0xFFB7C4FF); // tertiary-fixed-dim
const gText = Color(0xFFDCE2F4);
const gMuted = Color(0xFFBAC9CC);
const gLine = Color(0xFF3B494C);
const gWarn = Color(0xFFF59E0B);
const gErr = Color(0xFFFFB4AB);

// ===== SECTION 2: text styles (Plus Jakarta Sans for text, JetBrains Mono for small telemetry labels) =====
TextStyle gHead(double size, {FontWeight w = FontWeight.w700, Color c = gText}) =>
    GoogleFonts.plusJakartaSans(fontSize: size, fontWeight: w, color: c, letterSpacing: -0.3, height: 1.2);
TextStyle gBody(double size, {Color c = gText, FontWeight w = FontWeight.w400}) =>
    GoogleFonts.plusJakartaSans(fontSize: size, fontWeight: w, color: c, height: 1.45);
TextStyle gLabel(double size, {Color c = gCyan}) =>
    GoogleFonts.jetBrainsMono(fontSize: size, color: c, letterSpacing: 1.1, fontWeight: FontWeight.w600);

// ===== SECTION 3: widgets =====
/// Frosted card: faint white gradient, thin light border, big radius.
class GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  final Color? glow; // optional coloured border, for emphasis
  const GlassCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.onTap, this.glow});

  @override
  Widget build(BuildContext context) {
    final box = Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [
          Colors.white.withOpacity(0.08),
          Colors.white.withOpacity(0.02),
        ]),
        border: Border.all(color: glow != null ? glow!.withOpacity(0.45) : Colors.white.withOpacity(0.10)),
      ),
      child: child,
    );
    if (onTap == null) return box;
    return InkWell(onTap: onTap, borderRadius: BorderRadius.circular(24), child: box);
  }
}

/// Small pill label such as "LIVE" or "ARGO-V2".
class GChip extends StatelessWidget {
  final String text;
  final Color color;
  final IconData? icon;
  const GChip(this.text, {super.key, this.color = gCyan, this.icon});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(color: color.withOpacity(0.12), borderRadius: BorderRadius.circular(999), border: Border.all(color: color.withOpacity(0.35))),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 13, color: color), const SizedBox(width: 5)],
          Flexible(child: Text(text, overflow: TextOverflow.ellipsis, style: gLabel(10.5, c: color))),
        ]),
      );
}

/// Section heading with an icon, e.g. "ARGO Float Fleet Metrics".
class SectionTitle extends StatelessWidget {
  final String text;
  final IconData icon;
  final Widget? trailing;
  const SectionTitle(this.text, this.icon, {super.key, this.trailing});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 26, bottom: 12),
        child: Row(children: [
          Icon(icon, size: 20, color: gCyan),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: gHead(18))),
          if (trailing != null) trailing!,
        ]),
      );
}

/// Full-page background: deep navy with a soft cyan glow in the top corner.
class GlassBackdrop extends StatelessWidget {
  final Widget child;
  const GlassBackdrop({super.key, required this.child});

  @override
  Widget build(BuildContext context) => Container(
        decoration: const BoxDecoration(
          color: gBg,
          gradient: RadialGradient(center: Alignment(-0.9, -1.1), radius: 1.3, colors: [Color(0x2200E5FF), gBg]),
        ),
        child: child,
      );
}

/// Thousands separator: 12840 -> 12,840
String gNum(num n) {
  final s = n.round().toString();
  final b = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write(',');
    b.write(s[i]);
  }
  return b.toString();
}
