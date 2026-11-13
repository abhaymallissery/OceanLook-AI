// FILE: dashboard_page.dart - NEW (v6) PAGE 1, "Research Hub". Everything here comes from GET /dashboard (chat history + loaded ARGO data).
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'api.dart';
import 'api_extra.dart';
import 'glass.dart';

class DashboardPage extends StatefulWidget {
  final ValueListenable<int> reload;
  final void Function(String question) onAsk;
  const DashboardPage({super.key, required this.reload, required this.onAsk});
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  Json? _d;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.reload.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    widget.reload.removeListener(_load);
    super.dispose();
  }

  Future<void> _load() async {
    final d = await fetchDashboard();
    if (!mounted) return;
    setState(() {
      _d = d;
      _loading = false;
    });
  }

  List<Json> _list(dynamic v) => ((v as List?) ?? const []).cast<Json>();

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    final d = _d!;
    if (d['error'] != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('${d['error']}', textAlign: TextAlign.center, style: gBody(14, c: gErr))));
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000),
          child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
            Row(children: [
              Expanded(child: Text('TELEMETRY INTELLIGENCE', style: gLabel(11))),
              GChip('${d['questions']} QUESTIONS · ${d['sessions']} CHATS', color: gSky),
            ]),
            const SizedBox(height: 12),
            _focusCard(d),
            const SectionTitle('Why OceanLook?', Icons.help_outline),
            _useCase(),
            if (d['metrics'] != null) ...[
              SectionTitle('ARGO Fleet Metrics', Icons.speed, trailing: GChip((d['metrics'] as Json)['synthetic'] == true ? 'SYNTHETIC' : 'LIVE DATA', color: (d['metrics'] as Json)['synthetic'] == true ? gWarn : gCyan)),
              _metrics(d['metrics'] as Json),
            ],
            SectionTitle('Personalized Recommendations', Icons.auto_awesome, trailing: GChip('PATTERN LEARNED', color: gIndigo)),
            ..._recs(_list(d['recommendations'])),
            if (_list(d['hotspots']).isNotEmpty) ...[
              const SectionTitle('Top Monitored Regions', Icons.place_outlined),
              ..._list(d['hotspots']).map(_hotspot),
            ],
            if (_list(d['recent']).isNotEmpty) ...[
              const SectionTitle('Recent Questions', Icons.history),
              ..._list(d['recent']).map(_recent),
            ],
          ]),
        ),
      ),
    );
  }

  // ===== SECTION 1: hero card = research focus + the little summary + topic bars =====
  Widget _focusCard(Json d) {
    final topics = _list(d['topics']);
    final focus = d['focus'] as Json?;
    const colors = [gCyan, gSky, gIndigo, Color(0xFF2F7BFF)];
    return GlassCard(
      glow: gCyan,
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('PROFILING BEHAVIOR', style: gLabel(10.5, c: gMuted)),
        const SizedBox(height: 6),
        Text('Your Ocean Research Focus', style: gHead(28)),
        const SizedBox(height: 12),
        Text(d['summary'] as String, style: gBody(14, c: gMuted)), // the short plain-English summary from the backend
        if (focus != null) ...[
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Colors.black.withOpacity(0.25), borderRadius: BorderRadius.circular(20)),
            child: Row(children: [
              SizedBox(
                width: 84,
                height: 84,
                child: Stack(alignment: Alignment.center, children: [
                  CustomPaint(size: const Size(84, 84), painter: _Donut((focus['pct'] as num) / 100)),
                  Text('${focus['pct']}%', style: gHead(18, c: gCyan)),
                ]),
              ),
              const SizedBox(width: 16),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('TOP ANALYTICAL DOMAIN', style: gLabel(10, c: gMuted)),
                const SizedBox(height: 4),
                Text('${focus['label']}', style: gHead(17)),
              ])),
            ]),
          ),
          const SizedBox(height: 14),
          for (var i = 0; i < topics.length; i++) _bar(topics[i], colors[i % colors.length]),
        ],
      ]),
    );
  }

  Widget _bar(Json t, Color c) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Column(children: [
          Row(children: [
            Icon(Icons.circle, size: 8, color: c),
            const SizedBox(width: 8),
            Expanded(child: Text('${t['label']}', style: gBody(13.5))),
            Text('${t['pct']}%', style: gHead(14, c: c)),
          ]),
          const SizedBox(height: 5),
          ClipRRect(
            borderRadius: BorderRadius.circular(99),
            child: LinearProgressIndicator(value: (t['pct'] as num) / 100, minHeight: 6, color: c, backgroundColor: Colors.white.withOpacity(0.08)),
          ),
        ]),
      );

  // ===== SECTION 2: simple explanation of the use case (static text, same wording as note.md) =====
  Widget _useCase() {
    Widget row(IconData i, String h, String t) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(i, size: 20, color: gSky),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(h, style: gHead(14.5)),
              const SizedBox(height: 2),
              Text(t, style: gBody(13, c: gMuted)),
            ])),
          ]),
        );
    return GlassCard(
      child: Column(children: [
        row(Icons.warning_amber_rounded, 'The problem', 'ARGO floats collect millions of ocean readings, stored in technical NetCDF files. Getting one number normally needs programming and oceanography knowledge.'),
        row(Icons.chat_outlined, 'What OceanLook does', 'You ask in plain English, for example "average temperature at 500 m in the Arabian Sea in 2024". It finds the right profiles, removes bad readings, converts pressure to depth and calculates the answer.'),
        row(Icons.verified_outlined, 'Why you can trust it', 'The AI model never calculates a number. Python does, then runs checks on the result. Every answer shows the profiles it used and the checks it passed.'),
        row(Icons.school_outlined, 'Who it is for', 'Students, researchers and analysts in climate, fisheries and weather who need quick, checkable ocean numbers without writing code.'),
      ]),
    );
  }

  // ===== SECTION 3: metric tiles (from the loaded data) =====
  Widget _metrics(Json m) {
    final tiles = [
      ('PROFILE INGESTIONS', gNum(m['profiles'] as num), '${m['time_min']} to ${m['time_max']}', Icons.grid_view),
      ('FLOATS TRACKED', gNum(m['floats'] as num), 'in the loaded subset', Icons.sensors),
      ('DATA QUALITY (QC 1)', '${m['qc_good_pct']}%', 'readings flagged good', Icons.verified_outlined),
      ('DEEPEST READING', '${gNum(m['deepest_dbar'] as num)} dbar', 'pressure, about the same in metres', Icons.vertical_align_bottom),
    ];
    return LayoutBuilder(builder: (context, c) {
      final cols = c.maxWidth > 700 ? 4 : 2;
      final w = (c.maxWidth - 12.0 * (cols - 1)) / cols;
      return Wrap(spacing: 12, runSpacing: 12, children: [
        for (final t in tiles)
          SizedBox(
            width: w,
            child: GlassCard(
              padding: const EdgeInsets.all(14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [Expanded(child: Text(t.$1, style: gLabel(9.5, c: gMuted))), Icon(t.$4, size: 16, color: gCyan)]),
                const SizedBox(height: 8),
                FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(t.$2, style: gHead(26, c: gCyan))),
                const SizedBox(height: 4),
                Text(t.$3, style: gBody(11.5, c: gMuted)),
              ]),
            ),
          ),
      ]);
    });
  }

  // ===== SECTION 4: recommendations - tap one and Chat asks it =====
  static const _icons = {
    'UNEXPLORED REGION': Icons.explore_outlined,
    'OTHER VARIABLE': Icons.opacity,
    'COMPARE DEPTHS': Icons.compare_arrows,
    'VERTICAL PROFILE': Icons.vertical_align_bottom,
    'DATA QUALITY': Icons.verified_outlined,
  };

  List<Widget> _recs(List<Json> recs) => [
        for (final r in recs)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: GlassCard(
              onTap: () => widget.onAsk(r['question'] as String),
              padding: const EdgeInsets.all(14),
              child: Row(children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: BoxDecoration(color: gCyan.withOpacity(0.12), borderRadius: BorderRadius.circular(14)),
                  child: Icon(_icons['${r['tag']}'] ?? Icons.auto_awesome, color: gCyan, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('${r['tag']}', style: gLabel(10, c: gSky)),
                  const SizedBox(height: 3),
                  Text('${r['title']}', style: gBody(14)),
                ])),
                const Icon(Icons.arrow_forward, size: 18, color: gMuted),
              ]),
            ),
          ),
      ];

  Widget _hotspot(Json h) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: GlassCard(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(children: [
            const Icon(Icons.circle, size: 10, color: gCyan),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${h['region']}', style: gHead(15)),
              Text('${h['lat']}°N  ${h['lon']}°E  (centre of profiles)', style: gLabel(10.5, c: gMuted)),
            ])),
            GChip('${h['floats']} FLOATS · ${h['profiles']} PROFILES', color: gSky),
          ]),
        ),
      );

  Widget _recent(Json r) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: GlassCard(
          onTap: () => widget.onAsk(r['question'] as String),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(children: [
            Expanded(child: Text('${r['question']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: gBody(13))),
            const SizedBox(width: 8),
            GChip('${r['status']}'.toUpperCase(), color: r['status'] == 'ok' || r['status'] == 'docs' ? gCyan : gWarn),
          ]),
        ),
      );
}

class _Donut extends CustomPainter {
  final double frac;
  _Donut(this.frac);

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(6, 6, size.width - 12, size.height - 12);
    canvas.drawArc(rect, 0, 2 * math.pi, false, Paint()..style = PaintingStyle.stroke..strokeWidth = 9..color = Colors.white12);
    canvas.drawArc(rect, -math.pi / 2, 2 * math.pi * frac, false,
        Paint()..style = PaintingStyle.stroke..strokeWidth = 9..strokeCap = StrokeCap.round..color = gCyan);
  }

  @override
  bool shouldRepaint(_Donut old) => old.frac != frac;
}
