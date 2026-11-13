// FILE: chat_screen.dart - NEW (v6) PAGE 2, Chat, in the new glass design. Reuses AnswerCard (unchanged) to show each answer.
// Adds: History button (resume an old conversation), New chat, Edit query, Copy, recommended next questions.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'api.dart';
import 'api_extra.dart';
import 'answer_card.dart';
import 'glass.dart';
import 'history_sheet.dart';

class _Turn {
  final String question;
  Answer? answer; // null while loading
  final DateTime at;
  _Turn(this.question, {this.answer, DateTime? at}) : at = at ?? DateTime.now();
}

// Empty-screen suggestions; each maps to a supported question type.
const _starters = [
  ('TEMPERATURE AT DEPTH', 'What was the average temperature at 500 m in the Arabian Sea during 2024?'),
  ('COMPARE DEPTHS', 'Compare the average temperature at 100 metres and 1,000 metres in the Arabian Sea during 2024.'),
  ('SALINITY', 'What was the average salinity at 200 m in the Bay of Bengal during 2024?'),
  ('COVERAGE', 'How many ARGO profiles were recorded in the Arabian Sea during 2024?'),
  ('VERTICAL PROFILE', 'Show the average temperature profile of the Arabian Sea in 2024.'),
  ('CONCEPTS (RAG)', 'What does QC flag 1 mean?'),
];

// Quick-insert templates the user can tap to fill the input box
const _templates = [
  'What was the average temperature at ___ m in the Arabian Sea during 2024?',
  'Compare the average temperature at ___ m and ___ m in the Bay of Bengal during 2024.',
  'What was the average salinity at ___ m in the Arabian Sea during 2024?',
  'How many profiles were recorded in the Arabian Sea during 2024?',
  'Show the temperature profile of the Arabian Sea in 2024.',
];

class ChatScreen extends StatefulWidget {
  final VoidCallback? onAnswered; // lets the dashboard refresh after each answer
  const ChatScreen({super.key, this.onAnswered});
  @override
  State<ChatScreen> createState() => ChatScreenState();
}

class ChatScreenState extends State<ChatScreen> {
  final _turns = <_Turn>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  String _sid = 'app-${DateTime.now().millisecondsSinceEpoch}'; // one id per conversation; the backend remembers follow-ups by it
  List<Json> _recs = [];
  bool _showTemplates = false;

  @override
  void initState() {
    super.initState();
    _loadRecs();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  // ===== SECTION 1: recommended next questions (from /dashboard, "history aligned") =====
  Future<void> _loadRecs() async {
    final d = await fetchDashboard();
    if (!mounted) return;
    setState(() => _recs = ((d['recommendations'] as List?) ?? const []).cast<Json>());
  }

  // ===== SECTION 2: send, new chat, resume =====
  Future<void> send([String? text]) async {
    final q = (text ?? _input.text).trim();
    if (q.isEmpty) return;
    _input.clear();
    setState(() => _showTemplates = false);
    final t = _Turn(q);
    setState(() => _turns.add(t));
    _toEnd();
    final a = await askIn(q, _sid);
    if (!mounted) return;
    setState(() => t.answer = a);
    _toEnd();
    widget.onAnswered?.call();
    _loadRecs();
  }

  void _newChat() => setState(() {
        _turns.clear();
        _sid = 'app-${DateTime.now().millisecondsSinceEpoch}';
      });

  Future<void> _openHistory() async {
    final sid = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: gBg,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
      builder: (_) => const HistorySheet(),
    );
    if (sid != null) await _resume(sid);
  }

  Future<void> _resume(String sid) async {
    final j = await fetchSession(sid);
    if (!mounted) return;
    if (j['error'] != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${j['error']}')));
      return;
    }
    final rows = ((j['turns'] as List?) ?? const []).cast<Json>();
    setState(() {
      _sid = sid; // new questions continue this conversation
      _turns
        ..clear()
        ..addAll(rows.map((r) => _Turn('${r['question']}', answer: Answer.fromJson(r['answer'] as Json), at: DateTime.tryParse('${r['ts']}')?.toLocal())));
    });
    _toEnd();
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  String _clock(DateTime t) {
    final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
    return '$h:${t.minute.toString().padLeft(2, '0')} ${t.hour < 12 ? 'AM' : 'PM'}';
  }

  // ===== SECTION 3: layout =====
  @override
  Widget build(BuildContext context) => Column(children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 12, 4),
          child: Row(children: [
            Expanded(child: Text('Chat', style: gHead(22))),
            TextButton.icon(onPressed: _openHistory, icon: const Icon(Icons.history, size: 18), label: const Text('History')),
            TextButton.icon(onPressed: _newChat, icon: const Icon(Icons.add, size: 18), label: const Text('New')),
          ]),
        ),
        Expanded(child: _turns.isEmpty ? _welcome() : _stream()),
        _composer(),
      ]);

  Widget _welcome() => Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text('Explore the ocean through conversation.', textAlign: TextAlign.center, style: gHead(28)),
              const SizedBox(height: 8),
              Text('Ask about ocean temperature and salinity from ARGO floats. Every number comes from retrieved observations, not from the language model.',
                  textAlign: TextAlign.center, style: gBody(14, c: gMuted)),
              const SizedBox(height: 16),
              // How-to guide card
              _howToCard(),
              const SizedBox(height: 22),
              Text('Try one of these questions', style: gHead(18)),
              const SizedBox(height: 12),
              Wrap(spacing: 12, runSpacing: 12, children: [
                for (final s in _starters)
                  SizedBox(
                    width: 270,
                    child: GlassCard(
                      onTap: () => send(s.$2),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(s.$1, style: gLabel(10.5)),
                        const SizedBox(height: 8),
                        Text(s.$2, style: gBody(13.5)),
                      ]),
                    ),
                  ),
              ]),
            ]),
          ),
        ),
      );

  Widget _howToCard() => GlassCard(
        glow: gCyan,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.info_outline, color: gCyan, size: 18),
            const SizedBox(width: 8),
            Text('How to chat with OceanLook', style: gHead(16)),
          ]),
          const SizedBox(height: 10),
          Text('OceanLook queries verified ARGO ocean float measurements. You can ask naturally or follow up in conversation:', style: gBody(13.5, c: gMuted)),
          const SizedBox(height: 8),
          _rule(Icons.public, 'Regions', 'Arabian Sea, Bay of Bengal, Indian Ocean, Equatorial Indian Ocean (defaults to active region)'),
          _rule(Icons.calendar_today, 'Time period', 'Year (2024), month + year (January 2024), or leave blank to use the dataset period'),
          _rule(Icons.straighten, 'Depths', 'Numbers with units (e.g. 500 m, 100 metres), "surface" (100 m), or "deep" (1000 m)'),
          _rule(Icons.thermostat, 'Variables', 'Temperature (default) or salinity'),
          _rule(Icons.question_answer, 'Follow-ups', 'Ask "what about 200 m?" or "and for salinity?" — it remembers the conversation context'),
          const SizedBox(height: 10),
          Text('Example questions that work:', style: gBody(13, c: gCyan, w: FontWeight.w600)),
          const SizedBox(height: 4),
          _exampleLine('• "What is the average temperature at 500 m in the Arabian Sea?"'),
          _exampleLine('• "See how temperature changes from the surface down to 1800m"'),
          _exampleLine('• "Compare the surface layer with the deep layer in the Arabian Sea"'),
          _exampleLine('• "Compare salinity at 100 m and 1000 m in the Bay of Bengal during 2024"'),
          _exampleLine('• "How many profiles were recorded in the Arabian Sea during 2024?"'),
          _exampleLine('• "What does QC flag 1 mean?" (concepts & data documentation)'),
        ]),
      );

  Widget _rule(IconData icon, String label, String detail) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(icon, color: gCyan, size: 16),
          const SizedBox(width: 8),
          Expanded(child: RichText(
            text: TextSpan(children: [
              TextSpan(text: '$label: ', style: gBody(13, c: gText, w: FontWeight.w600)),
              TextSpan(text: detail, style: gBody(13, c: gMuted)),
            ]),
          )),
        ]),
      );

  Widget _exampleLine(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 2),
        child: Text(text, style: gBody(12.5, c: gMuted)),
      );

  Widget _stream() => ListView.builder(
        controller: _scroll,
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
        itemCount: _turns.length + 1,
        itemBuilder: (_, i) {
          if (i == _turns.length) return _next();
          final t = _turns[i];
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 900),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                _userBubble(t),
                if (t.answer == null)
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(children: [
                      const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                      const SizedBox(width: 12),
                      Expanded(child: Text('Interpreting question and querying ARGO profiles…', style: gBody(13, c: gMuted))),
                    ]),
                  )
                else ...[
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Row(children: [
                      const Icon(Icons.waves, size: 18, color: gCyan),
                      const SizedBox(width: 8),
                      Text('OceanLook ARGO Engine', style: gHead(16)),
                      const SizedBox(width: 8),
                      if (t.answer!.parser.isNotEmpty) GChip('PARSER: ${t.answer!.parser.toUpperCase()}', color: gIndigo),
                      const Spacer(),
                      Text(_clock(t.at), style: gLabel(10.5, c: gMuted)),
                    ]),
                  ),
                  AnswerCard(t.answer!),
                  // Show help tip when the answer is an error
                  if (t.answer!.status == 'unsupported' || t.answer!.status == 'error') _errorHelp(t.answer!),
                ],
                const SizedBox(height: 20),
              ]),
            ),
          );
        },
      );

  Widget _errorHelp(Answer a) {
    final msg = a.message.toLowerCase();
    final tips = <String>[];
    if (msg.contains('no year') || msg.contains('time period')) {
      tips.add('Add a year or month — e.g. "in 2024" or "during January 2024"');
    }
    if (msg.contains('no known region') || msg.contains('region')) {
      tips.add('Use an exact region name: Arabian Sea, Bay of Bengal, Indian Ocean, or Equatorial Indian Ocean');
    }
    if (msg.contains('no depth') || msg.contains('depths')) {
      tips.add('Add a depth with units — e.g. "at 500 m" or "at 100 metres and 1000 metres"');
    }
    if (tips.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(top: 4, bottom: 4),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: gCyan.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: gCyan.withValues(alpha: 0.25)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.lightbulb_outline, color: gCyan, size: 16),
          const SizedBox(width: 6),
          Text('Tip: Try rephrasing your question', style: gBody(13, c: gCyan, w: FontWeight.w600)),
        ]),
        const SizedBox(height: 6),
        for (final tip in tips)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text('• $tip', style: gBody(12.5, c: gMuted)),
          ),
      ]),
    );
  }

  Widget _userBubble(_Turn t) => Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        Text('You · ${_clock(t.at)}', style: gLabel(10.5, c: gMuted)),
        const SizedBox(height: 6),
        Container(
          margin: const EdgeInsets.only(left: 40),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(color: gCardHigh, borderRadius: BorderRadius.circular(18), border: Border.all(color: Colors.white.withValues(alpha: 0.08))),
          child: Text(t.question, style: gBody(14.5)),
        ),
        Row(mainAxisSize: MainAxisSize.min, children: [
          TextButton.icon(onPressed: () => _input.text = t.question, icon: const Icon(Icons.edit, size: 14), label: const Text('Edit query')),
          TextButton.icon(onPressed: () => Clipboard.setData(ClipboardData(text: t.question)), icon: const Icon(Icons.copy, size: 14), label: const Text('Copy')),
        ]),
        const SizedBox(height: 6),
      ]);

  // Recommended next inquiries, shown after the last answer.
  Widget _next() {
    if (_recs.isEmpty) return const SizedBox.shrink();
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text('Recommended Next Inquiries', style: gHead(17))),
            GChip('HISTORY ALIGNED', color: gIndigo),
          ]),
          const SizedBox(height: 10),
          for (final r in _recs.take(3))
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: GlassCard(
                onTap: () => send('${r['question']}'),
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Row(children: [
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      if (r['tag'] != null) ...[
                        GChip('${r['tag']}', color: gCyan),
                        const SizedBox(height: 6),
                      ],
                      Text('${r['title']}', style: gBody(13.5, w: FontWeight.w600)),
                      if (r['question'] != null && '${r['question']}' != '${r['title']}') ...[
                        const SizedBox(height: 3),
                        Text('Query: "${r['question']}"', style: gBody(12, c: gMuted)),
                      ],
                    ]),
                  ),
                  const SizedBox(width: 8),
                  const Icon(Icons.arrow_forward_ios, color: gCyan, size: 14),
                ]),
              ),
            ),
        ]),
      ),
    );
  }

  Widget _composer() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              // Templates dropdown
              if (_showTemplates)
                Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  decoration: BoxDecoration(
                    color: gCard,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: gLine.withValues(alpha: 0.5)),
                  ),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                      child: Row(children: [
                        const Icon(Icons.auto_fix_high, size: 14, color: gCyan),
                        const SizedBox(width: 6),
                        Expanded(child: Text('Question templates — tap to fill, then edit the blanks (___)', style: gBody(12, c: gMuted))),
                        IconButton(
                          icon: const Icon(Icons.close, size: 16, color: gMuted),
                          onPressed: () => setState(() => _showTemplates = false),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                        ),
                      ]),
                    ),
                    for (final t in _templates)
                      InkWell(
                        onTap: () {
                          _input.text = t;
                          // Position cursor at the first blank
                          final blankIdx = t.indexOf('___');
                          if (blankIdx >= 0) {
                            _input.selection = TextSelection(baseOffset: blankIdx, extentOffset: blankIdx + 3);
                          }
                          setState(() => _showTemplates = false);
                        },
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                          child: Align(alignment: Alignment.centerLeft, child: Text(t, style: gBody(13))),
                        ),
                      ),
                  ]),
                ),
              // Input row
              TextField(
                controller: _input,
                onSubmitted: send,
                style: gBody(14.5),
                decoration: InputDecoration(
                  hintText: 'Ask about temperature or salinity at a depth, in a region, during a year…',
                  hintStyle: gBody(13, c: gMuted),
                  filled: true,
                  fillColor: gCard,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(28), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.10))),
                  enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(28), borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.10))),
                  prefixIcon: Padding(
                    padding: const EdgeInsets.only(left: 6),
                    child: IconButton(
                      icon: Icon(_showTemplates ? Icons.keyboard_arrow_down : Icons.auto_fix_high, color: gCyan, size: 20),
                      onPressed: () => setState(() => _showTemplates = !_showTemplates),
                      tooltip: 'Question templates',
                    ),
                  ),
                  suffixIcon: Padding(
                    padding: const EdgeInsets.all(6),
                    child: IconButton.filled(style: IconButton.styleFrom(backgroundColor: gCyan, foregroundColor: gBg), icon: const Icon(Icons.arrow_upward), onPressed: () => send()),
                  ),
                ),
              ),
            ]),
          ),
        ),
      );
}
