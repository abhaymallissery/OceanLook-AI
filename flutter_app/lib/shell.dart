// FILE: shell.dart - NEW (v6) the frame around the three pages: top bar (data status), collapsible glass rail sidebar on wide screens, bottom bar on phones.
import 'package:flutter/material.dart';
import 'api.dart';
import 'chat_screen.dart';
import 'dashboard_page.dart';
import 'glass.dart';
import 'tuning_page.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> with SingleTickerProviderStateMixin {
  int _tab = 0; // 0 Dashboard, 1 Chat, 2 Fine-tuning
  final _chat = GlobalKey<ChatScreenState>();
  final _reload = ValueNotifier<int>(0); // bumped when a page should re-read the backend
  Future<Json?> _health = health();
  bool _railExpanded = false;

  late final AnimationController _railAnim;
  late final Animation<double> _railWidth;

  @override
  void initState() {
    super.initState();
    _railAnim = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 220),
    );
    _railWidth = Tween<double>(begin: 64, end: 200).animate(
      CurvedAnimation(parent: _railAnim, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _railAnim.dispose();
    super.dispose();
  }

  void _toggleRail() {
    setState(() => _railExpanded = !_railExpanded);
    if (_railExpanded) {
      _railAnim.forward();
    } else {
      _railAnim.reverse();
    }
  }

  void _go(int i) {
    setState(() {
      _tab = i;
      _health = health();
    });
    _reload.value++;
  }

  // A recommendation on the dashboard was tapped: open Chat and ask it.
  void _askInChat(String q) {
    _go(1);
    WidgetsBinding.instance.addPostFrameCallback((_) => _chat.currentState?.send(q));
  }

  static const _items = [
    (Icons.insights_outlined, Icons.insights, 'Research Hub'),
    (Icons.chat_bubble_outline, Icons.chat_bubble, 'Chat'),
    (Icons.tune_outlined, Icons.tune, 'Fine-tuning'),
  ];

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    final pages = IndexedStack(index: _tab, children: [
      DashboardPage(reload: _reload, onAsk: _askInChat),
      ChatScreen(key: _chat, onAnswered: () => _reload.value++),
      TuningPage(reload: _reload),
    ]);
    return Scaffold(
      backgroundColor: gBg,
      body: GlassBackdrop(
        child: SafeArea(
          child: Column(children: [
            _topBar(),
            Expanded(
              child: wide
                  ? Row(children: [
                      _glassRail(),
                      Expanded(child: pages),
                    ])
                  : pages,
            ),
            if (!wide)
              NavigationBar(
                backgroundColor: gLow,
                indicatorColor: gCyan.withValues(alpha: 0.18),
                selectedIndex: _tab,
                onDestinationSelected: _go,
                destinations: [
                  for (final i in _items) NavigationDestination(icon: Icon(i.$1, color: gMuted), selectedIcon: Icon(i.$2, color: gCyan), label: i.$3),
                ],
              ),
          ]),
        ),
      ),
    );
  }

  // ===== Sleek Glass Rail =====
  Widget _glassRail() {
    return AnimatedBuilder(
      animation: _railWidth,
      builder: (context, child) {
        final w = _railWidth.value;
        final showLabels = w > 120;
        return Container(
          width: w,
          margin: const EdgeInsets.only(left: 8, top: 4, bottom: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [
              Colors.white.withValues(alpha: 0.06),
              Colors.white.withValues(alpha: 0.02),
            ]),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
          ),
          child: Column(
            children: [
              const SizedBox(height: 12),
              // Expand / Collapse arrow button
              Align(
                alignment: showLabels ? Alignment.centerRight : Alignment.center,
                child: Padding(
                  padding: EdgeInsets.only(right: showLabels ? 8 : 0),
                  child: IconButton(
                    icon: AnimatedRotation(
                      turns: _railExpanded ? 0.5 : 0.0,
                      duration: const Duration(milliseconds: 220),
                      child: const Icon(Icons.chevron_right_rounded, color: gMuted, size: 22),
                    ),
                    onPressed: _toggleRail,
                    tooltip: _railExpanded ? 'Collapse sidebar' : 'Expand sidebar',
                    splashRadius: 18,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              // Nav items
              for (var idx = 0; idx < _items.length; idx++) _railItem(idx, showLabels),
              const Spacer(),
            ],
          ),
        );
      },
    );
  }

  Widget _railItem(int idx, bool showLabels) {
    final selected = _tab == idx;
    final item = _items[idx];
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 6),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _go(idx),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            color: selected ? gCyan.withValues(alpha: 0.14) : Colors.transparent,
          ),
          child: Row(
            children: [
              // Glowing vertical indicator
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 3,
                height: 22,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(3),
                  color: selected ? gCyan : Colors.transparent,
                  boxShadow: selected
                      ? [BoxShadow(color: gCyan.withValues(alpha: 0.5), blurRadius: 8, spreadRadius: 1)]
                      : [],
                ),
              ),
              const SizedBox(width: 8),
              Icon(
                selected ? item.$2 : item.$1,
                color: selected ? gCyan : gMuted,
                size: 22,
              ),
              if (showLabels) ...[
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    item.$3,
                    style: gBody(13, c: selected ? gCyan : gMuted, w: selected ? FontWeight.w600 : FontWeight.w400),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  // Top bar: everything on the right is read from /health (nothing hard-coded).
  Widget _topBar() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
        child: Row(children: [
          const Icon(Icons.waves, color: gCyan),
          const SizedBox(width: 8),
          Text('OceanLook', style: gHead(20)),
          const Spacer(),
          FutureBuilder<Json?>(
            future: _health,
            builder: (context, snap) {
              final h = snap.data;
              if (snap.connectionState != ConnectionState.done) return const GChip('CONNECTING', color: gMuted);
              if (h == null) return const GChip('BACKEND OFFLINE', color: gErr, icon: Icons.cloud_off);
              if (h['loaded'] != true) return const GChip('NO DATA LOADED', color: gErr);
              if (h['synthetic'] == true) return const GChip('SYNTHETIC DEMO DATA', color: gWarn, icon: Icons.science_outlined);
              return GChip('ARGO · ${h['floats']} FLOATS · ${h['profiles']} PROFILES', icon: Icons.sensors);
            },
          ),
        ]),
      );
}
