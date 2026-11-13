// FILE: answer_card.dart - renders one backend answer. CHANGED (v2): docs answers, synthetic strip, agent steps, extra results, checks.
import 'dart:math' as math;
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'api.dart';
import 'main.dart';

// ===== SECTION 1: AnswerCard - chooses which cards to show for an answer =====
/// Renders only fields the backend returned; no placeholder or demo values.
class AnswerCard extends StatelessWidget {
  final Answer a;
  const AnswerCard(this.a, {super.key});

  @override
  Widget build(BuildContext context) {
    if (a.status == 'docs') return _docs(); // CHANGED (v2): concept question answered from the notes
    if (a.status == 'error' || a.status == 'unsupported' || a.status == 'blocked') {
      return _box(Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Icon(Icons.error_outline, color: danger),
        const SizedBox(width: 12),
        Expanded(child: Text(a.message, style: const TextStyle(color: danger))),
      ]));
    }
    final r = a.result!;
    final unit = r['unit'] as String? ?? '';
    final series = (r['series'] as List).cast<Json>();
    final curve = (r['curve'] as List).cast<Json>();
    final obs = (r['observations'] as List).cast<Json>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (a.synthetic) _strip('SYNTHETIC DEMO DATA - these values are invented, not real ARGO measurements.', warn), // CHANGED (v2)
      if (a.status == 'unverified') _strip('This result FAILED verification checks. Do not use it.', danger), // CHANGED (v2)
      _box(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _label('HOW YOUR QUESTION WAS UNDERSTOOD'),
        const SizedBox(height: 8),
        _chips(a.interpretation!),
      ])),
      _box(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (a.explanation.isNotEmpty) ...[
          Text(a.explanation, style: const TextStyle(fontSize: 16, height: 1.5)),
          const SizedBox(height: 16),
        ],
        Wrap(spacing: 12, runSpacing: 12, children: _tiles(r, series, unit)),
      ])),
      if (curve.where((s) => s['value'] != null).length > 1)
        _box(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _label('${(r['variable'] as String).toUpperCase()} VS DEPTH  (profile means across selected profiles)'),
          const SizedBox(height: 12),
          _chart(curve, a.interpretation!['intent'] == 'depth_profile' ? [] : series, unit),
        ])),
      if (obs.isNotEmpty) _box(_table(obs, r, unit)),
      for (final e in a.extra) // CHANGED (v2): further queries run by the agent
        AnswerCard(Answer(status: (e['result'] as Json)['status'] as String, interpretation: e['interpretation'] as Json, result: e['result'] as Json, synthetic: a.synthetic)),
      if (a.steps.isNotEmpty) _box(_steps()),
      _box(_provenance(r)),
    ]);
  }

  // ===== SECTION 2: new cards (v2) - notes answer, coloured strip, agent steps =====
  Widget _docs() => _box(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _label('FROM THE OCEANLOOK NOTES (retrieved text, not generated)'),
        const SizedBox(height: 8),
        Text(a.explanation, style: const TextStyle(fontSize: 15, height: 1.5)),
        for (final d in a.docs)
          Padding(padding: const EdgeInsets.only(top: 6), child: Text('• ${d['title']} - ${d['source']}', style: const TextStyle(fontSize: 12, color: muted))),
      ]));

  Widget _strip(String text, Color c) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: c.withOpacity(0.12), borderRadius: BorderRadius.circular(8), border: Border.all(color: c)),
        child: Text(text, style: TextStyle(color: c, fontSize: 13, fontWeight: FontWeight.w600)),
      );

  Widget _steps() => Theme(
        data: ThemeData.dark().copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: _label('AGENT STEPS (what the agent decided to do)'),
          children: [for (final s in a.steps) Align(alignment: Alignment.centerLeft, child: Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(s, style: const TextStyle(fontSize: 12, color: muted, fontFamily: 'monospace'))))],
        ),
      );

  // ===== SECTION 3: shared building blocks =====
  Widget _box(Widget child) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: card, borderRadius: BorderRadius.circular(8), border: Border.all(color: border)),
        child: child,
      );

  Widget _label(String t) => Text(t, style: const TextStyle(fontSize: 11, color: muted, letterSpacing: 1));

  // ===== SECTION 4: interpretation chips, metric tiles, chart, table, provenance =====
  Widget _chips(Json q) {
    final depths = (q['depths_m'] as List).map((d) => '${d is num && d == d.roundToDouble() ? d.toInt() : d} m').join(' & ');
    final items = <String>[
      'intent: ${q['intent']}',
      if (q['intent'] != 'count_profiles') '${q['stat']} ${q['variable']}',
      if (q['region'] != null) '${q['region']}' else 'bbox ${q['bbox']}',
      '${q['start']} → ${q['end']}',
      if (depths.isNotEmpty) depths,
    ];
    return Wrap(spacing: 8, runSpacing: 8, children: [
      for (final t in items)
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(color: panel, borderRadius: BorderRadius.circular(4), border: Border.all(color: border)),
          child: Text(t, style: const TextStyle(fontSize: 12, fontFamily: 'monospace', color: primary)),
        ),
    ]);
  }

  List<Widget> _tiles(Json r, List<Json> s, String unit) {
    String f(num? v) => v == null ? '—' : v.toStringAsFixed(2);
    final intent = r['intent'];
    final out = <Widget>[];
    if (intent == 'mean_at_depth' && s.isNotEmpty) {
      out.add(_tile((a.interpretation!['stat'] as String).toUpperCase(), '${f(s[0]['value'])} $unit', accent));
      out.add(_tile('STD DEV', s[0]['std'] == null ? '—' : '${f(s[0]['std'])} $unit', null));
      out.add(_tile('PROFILES USED', '${s[0]['n_profiles']} of ${r['n_profiles_in_scope']}', null));
      out.add(_tile('FLOATS', '${s[0]['n_floats']}', null));
    } else if (intent == 'compare_depths' && s.length == 2) {
      for (final x in s) {
        out.add(_tile('AT ${x['depth_m'].toStringAsFixed(0)} m', '${f(x['value'])} $unit', accent));
      }
      out.add(_tile('DIFFERENCE', r['difference'] == null ? '—' : '${(r['difference'] as num) >= 0 ? '+' : ''}${f(r['difference'])} $unit', null));
      out.add(_tile('PROFILES USED', '${s[0]['n_profiles']} / ${s[1]['n_profiles']}', null));
    } else {
      out.add(_tile('PROFILES IN SCOPE', '${r['n_profiles_in_scope']}', accent));
      out.add(_tile('FLOATS', '${r['n_floats_in_scope']}', null));
    }
    return out;
  }

  Widget _tile(String label, String value, Color? c) => Container(
        width: 190,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: panel, borderRadius: BorderRadius.circular(8), border: Border.all(color: border)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _label(label),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 20, fontFamily: 'monospace', fontWeight: FontWeight.w600, color: c ?? onSurface)),
        ]),
      );

  Widget _chart(List<Json> curve, List<Json> marked, String unit) {
    final pts = [for (final s in curve) if (s['value'] != null) FlSpot((s['value'] as num).toDouble(), -(s['depth_m'] as num).toDouble())];
    final dots = [for (final s in marked) if (s['value'] != null) FlSpot((s['value'] as num).toDouble(), -(s['depth_m'] as num).toDouble())];
    final maxDepth = pts.map((p) => -p.y).reduce(math.max);
    final bottom = -(maxDepth / 200).ceil() * 200.0;
    const hidden = AxisTitles(sideTitles: SideTitles(showTitles: false));
    const small = TextStyle(fontSize: 10, color: muted, fontFamily: 'monospace');
    return SizedBox(
      height: 340,
      child: LineChart(LineChartData(
        minY: bottom,
        maxY: 0,
        lineTouchData: const LineTouchData(enabled: false),
        gridData: const FlGridData(show: true),
        borderData: FlBorderData(show: true, border: Border.all(color: border)),
        titlesData: FlTitlesData(
          topTitles: hidden,
          rightTitles: hidden,
          leftTitles: AxisTitles(
            axisNameWidget: const Text('depth (m)', style: small),
            axisNameSize: 20,
            sideTitles: SideTitles(showTitles: true, reservedSize: 48, interval: 200, getTitlesWidget: (v, m) => Text('${(-v).round()}', style: small)),
          ),
          bottomTitles: AxisTitles(
            axisNameWidget: Text(unit, style: small),
            axisNameSize: 20,
            sideTitles: SideTitles(showTitles: true, reservedSize: 24, getTitlesWidget: (v, m) => Text(v.toStringAsFixed(1), style: small)),
          ),
        ),
        lineBarsData: [
          LineChartBarData(spots: pts, isCurved: false, color: primary, barWidth: 2, dotData: const FlDotData(show: true)),
          if (dots.isNotEmpty)
            LineChartBarData(spots: dots, barWidth: 0, color: accent, dotData: FlDotData(show: true, getDotPainter: (a, b, c, d) => FlDotCirclePainter(radius: 6, color: accent))),
        ],
      )),
    );
  }

  Widget _table(List<Json> obs, Json r, String unit) {
    const mono = TextStyle(fontSize: 12, fontFamily: 'monospace');
    final shown = obs.take(50).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _label('OBSERVATIONS USED  (showing ${shown.length} of ${r['n_observations']})'),
      const SizedBox(height: 8),
      SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTable(
          headingRowHeight: 32,
          dataRowMinHeight: 28,
          dataRowMaxHeight: 28,
          columns: [for (final h in ['WMO float', 'Cycle', 'Time (UTC)', 'Lat', 'Lon', 'Depth m', 'Value $unit', 'Bracket m']) DataColumn(label: Text(h, style: const TextStyle(fontSize: 11, color: muted)))],
          rows: [
            for (final o in shown)
              DataRow(cells: [
                DataCell(Text('${o['platform_number']}', style: mono.copyWith(color: primary))),
                DataCell(Text('${o['cycle_number']}', style: mono)),
                DataCell(Text('${o['time']}'.substring(0, 16).replaceFirst('T', ' '), style: mono)),
                DataCell(Text((o['latitude'] as num).toStringAsFixed(2), style: mono)),
                DataCell(Text((o['longitude'] as num).toStringAsFixed(2), style: mono)),
                DataCell(Text((o['target_depth_m'] as num).toStringAsFixed(0), style: mono)),
                DataCell(Text((o['value'] as num).toStringAsFixed(3), style: mono.copyWith(color: accent))),
                DataCell(Text('${(o['bracket_lo_m'] as num).toStringAsFixed(0)}–${(o['bracket_hi_m'] as num).toStringAsFixed(0)}', style: mono)),
              ]),
          ],
        ),
      ),
    ]);
  }

  Widget _provenance(Json r) => Theme(
        data: ThemeData.dark().copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: _label('METHOD, QUALITY CONTROL & PROVENANCE'),
          children: [
            Align(
              alignment: Alignment.centerLeft,
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Method: ${r['method']}', style: const TextStyle(fontSize: 13, color: muted)),
                const SizedBox(height: 6),
                Text('QC: ${r['qc_rule']}', style: const TextStyle(fontSize: 13, color: muted)),
                const SizedBox(height: 6),
                Text('Source: ${r['source']}', style: const TextStyle(fontSize: 13, color: muted)),
                // CHANGED (v2): the run-time verification checks are listed so the user can see what was verified
                for (final c in ((r['checks'] as List?) ?? []).cast<Json>()) Padding(padding: const EdgeInsets.only(top: 2), child: Text('${c['ok'] == true ? '✓' : '✗'} ${c['name']}', style: TextStyle(fontSize: 12, color: c['ok'] == true ? accent : danger))),
                for (final c in (r['caveats'] as List)) Padding(padding: const EdgeInsets.only(top: 6), child: Text('⚠ $c', style: const TextStyle(fontSize: 13, color: warn))),
              ]),
            ),
          ],
        ),
      );
}
