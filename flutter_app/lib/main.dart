// FILE: main.dart - app entry, theme and colour tokens from the Stitch design system.
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'shell.dart'; // CHANGED (v6): the app now opens the 3-page shell; chat_page.dart is kept but no longer used

// ===== SECTION 1: colour tokens ===== from the Stitch "Oceanic Telemetry Terminal" design system.
const surface = Color(0xFF041329);
const panel = Color(0xFF0D1C32);
const card = Color(0xFF112036);
const cardHigh = Color(0xFF1C2A41);
const primary = Color(0xFF89CEFF);
const accent = Color(0xFF4FDBC8);
const onSurface = Color(0xFFD6E3FF);
const muted = Color(0xFFBEC8D2);
const border = Color(0x3389CEFF);
const warn = Color(0xFFF59E0B);
const danger = Color(0xFFFFB4AB);

// ===== SECTION 2: app entry and dark theme =====
void main() => runApp(const OceanLookApp());

class OceanLookApp extends StatelessWidget {
  const OceanLookApp({super.key});

  @override
  Widget build(BuildContext context) {
    final base = ThemeData.dark(useMaterial3: true);
    return MaterialApp(
      title: 'OceanLook',
      debugShowCheckedModeBanner: false,
      theme: base.copyWith(
        scaffoldBackgroundColor: surface,
        colorScheme: const ColorScheme.dark(primary: primary, surface: surface, onSurface: onSurface, error: danger),
        textTheme: GoogleFonts.manropeTextTheme(base.textTheme).apply(bodyColor: onSurface, displayColor: onSurface),
      ),
      home: const AppShell(),
    );
  }
}

typedef FloatChatApp = OceanLookApp;
