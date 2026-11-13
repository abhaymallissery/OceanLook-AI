// FILE: history_sheet.dart - NEW (v6) the HISTORY option: a sheet that lists saved conversations (GET /history) and returns the one to resume.
import 'package:flutter/material.dart';
import 'api.dart';
import 'api_extra.dart';
import 'glass.dart';

class HistorySheet extends StatefulWidget {
  const HistorySheet({super.key});
  @override
  State<HistorySheet> createState() => _HistorySheetState();
}

class _HistorySheetState extends State<HistorySheet> {
  List<Json> _all = [];
  bool _loading = true;
  String? _error;
  String _filter = 'All';
  String _search = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final j = await fetchHistory();
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = j['error'] as String?;
      _all = ((j['sessions'] as List?) ?? const []).cast<Json>();
    });
  }

  Future<void> _delete(String sid) async {
    await deleteSession(sid);
    _load();
  }

  // ===== SECTION 1: filter by chip and by search text =====
  List<Json> get _shown => _all.where((s) {
        final okTag = _filter == 'All' || '${s['tag']}'.toLowerCase() == _filter.toLowerCase();
        final q = _search.toLowerCase();
        final okText = q.isEmpty || '${s['title']} ${s['region']} ${s['preview']}'.toLowerCase().contains(q);
        return okTag && okText;
      }).toList();

  // ===== SECTION 2: group by day =====
  String _day(DateTime t) {
    final now = DateTime.now();
    final d = DateTime(t.year, t.month, t.day);
    final today = DateTime(now.year, now.month, now.day);
    final diff = today.difference(d).inDays;
    if (diff <= 0) return 'Today';
    if (diff == 1) return 'Yesterday';
    return 'Earlier';
  }

  String _clock(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    final groups = <String, List<Json>>{};
    for (final s in _shown) {
      final t = DateTime.tryParse('${s['last']}')?.toLocal() ?? DateTime.now();
      groups.putIfAbsent(_day(t), () => []).add(s);
    }
    return SafeArea(
      child: FractionallySizedBox(
        heightFactor: 0.92,
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 8, 4),
            child: Row(children: [
              Expanded(child: Text('History', style: gHead(24))),
              IconButton(icon: const Icon(Icons.close, color: gMuted), onPressed: () => Navigator.pop(context)),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: TextField(
              onChanged: (v) => setState(() => _search = v),
              style: gBody(14),
              decoration: InputDecoration(
                hintText: 'Filter by region, topic or text',
                hintStyle: gBody(14, c: gMuted),
                prefixIcon: const Icon(Icons.search, color: gMuted),
                filled: true,
                fillColor: gCard,
                contentPadding: const EdgeInsets.symmetric(vertical: 12),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
              ),
            ),
          ),
          SizedBox(
            height: 54,
            child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10), children: [
              for (final f in const ['All', 'Temperature', 'Salinity', 'Concepts'])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(f, style: gBody(12.5, c: _filter == f ? gBg : gText, w: FontWeight.w600)),
                    selected: _filter == f,
                    selectedColor: gCyan,
                    backgroundColor: gCard,
                    showCheckmark: false,
                    onSelected: (_) => setState(() => _filter = f),
                  ),
                ),
            ]),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Text(_error!, style: gBody(14, c: gErr)))
                    : groups.isEmpty
                        ? Center(child: Text(_all.isEmpty ? 'No conversations yet. Ask a question in Chat and it appears here.' : 'Nothing matches this filter.', textAlign: TextAlign.center, style: gBody(14, c: gMuted)))
                        : ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 24), children: [
                            for (final g in groups.entries) ...[
                              Padding(
                                padding: const EdgeInsets.only(top: 14, bottom: 8),
                                child: Row(children: [Text(g.key, style: gHead(20)), const SizedBox(width: 8), GChip('${g.value.length} CHATS', color: gSky)]),
                              ),
                              for (final s in g.value) _card(s, _clock(DateTime.tryParse('${s['last']}')?.toLocal() ?? DateTime.now())),
                            ],
                          ]),
          ),
        ]),
      ),
    );
  }

  // ===== SECTION 3: one conversation card =====
  Widget _card(Json s, String clock) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: GlassCard(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              GChip('${s['tag']}'.toUpperCase()),
              const SizedBox(width: 8),
              if ('${s['region']}'.isNotEmpty) Flexible(child: GChip('${s['region']}'.toUpperCase(), color: gIndigo)),
              const Spacer(),
              Text(clock, style: gLabel(11, c: gMuted)),
            ]),
            const SizedBox(height: 10),
            Text('${s['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: gHead(16)),
            if ('${s['preview']}'.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('${s['preview']}', maxLines: 3, overflow: TextOverflow.ellipsis, style: gBody(13, c: gMuted)),
            ],
            const SizedBox(height: 10),
            Text('${s['messages']} messages', style: gLabel(10.5, c: gMuted)),
            const SizedBox(height: 10),
            Row(children: [
              FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: gCyan, foregroundColor: gBg),
                onPressed: () => Navigator.pop(context, '${s['session_id']}'),
                icon: const Icon(Icons.north_east, size: 16),
                label: const Text('Resume Chat'),
              ),
              const Spacer(),
              IconButton(tooltip: 'Delete', icon: const Icon(Icons.delete_outline, color: gMuted), onPressed: () => _delete('${s['session_id']}')),
            ]),
          ]),
        ),
      );
}
