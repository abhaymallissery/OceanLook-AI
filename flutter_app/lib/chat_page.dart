// FILE: chat_page.dart - main screen: sidebar, data banner, message stream, input box. CHANGED (v2): concept-question suggestion.
import 'package:flutter/material.dart';
import 'api.dart';
import 'answer_card.dart';
import 'main.dart';

class _Turn {
  final String question;
  Answer? answer; // null while loading
  _Turn(this.question);
}

// ===== SECTION 1: suggestion cards on the empty screen (each maps to a supported question type) =====
const _suggestions = [
  ('THERMAL STRATIFICATION', 'Compare the average temperature at 100 metres and 1,000 metres in the Arabian Sea during 2024.'),
  ('SALINITY', 'What was the average salinity at 200 m in the Bay of Bengal during 2024?'),
  ('COVERAGE', 'How many ARGO profiles were recorded in the Arabian Sea during 2024?'),
  ('CONCEPTS (RAG)', 'What does QC flag 1 mean?'), // CHANGED (v2): answered from the retrieved notes
];

class ChatPage extends StatefulWidget {
  const ChatPage({super.key});
  @override
  State<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> {
  final _turns = <_Turn>[];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  Future<Json?> _health = health();

  // ===== SECTION 2: sending a question and scrolling =====
  Future<void> _send([String? text]) async {
    final q = (text ?? _input.text).trim();
    if (q.isEmpty) return;
    _input.clear();
    final t = _Turn(q);
    setState(() => _turns.add(t));
    _toEnd();
    final a = await ask(q);
    if (!mounted) return;
    setState(() => t.answer = a);
    _toEnd();
  }

  void _toEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      });

  void _reset() => setState(() {
        _turns.clear();
        _health = health();
      });

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;
    return Scaffold(
      drawer: wide ? null : Drawer(backgroundColor: panel, child: _sidebar()),
      appBar: wide ? null : AppBar(backgroundColor: panel, title: const Text('OceanLook')),
      body: Row(children: [
        if (wide) SizedBox(width: 280, child: Container(color: panel, child: _sidebar())),
        Expanded(child: Column(children: [
          _banner(),
          Expanded(child: _turns.isEmpty ? _welcome() : _stream()),
          _composer(),
        ])),
      ]),
    );
  }

  // ===== SECTION 3: sidebar, banner (read from /health), welcome screen, message stream, input box =====
  Widget _sidebar() => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Row(children: [
              Icon(Icons.waves, color: primary),
              SizedBox(width: 8),
              Text('OceanLook', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              Spacer(),
              Text('SIH25040', style: TextStyle(fontSize: 11, color: muted, fontFamily: 'monospace')),
            ]),
            const SizedBox(height: 16),
            OutlinedButton.icon(onPressed: _reset, icon: const Icon(Icons.add, size: 18), label: const Text('New query')),
            const SizedBox(height: 20),
            const Text('THIS SESSION', style: TextStyle(fontSize: 11, color: muted, letterSpacing: 1)),
            const SizedBox(height: 6),
            Expanded(
              child: ListView(children: [
                for (final t in _turns)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Text(t.question, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13, color: muted)),
                  ),
              ]),
            ),
          ]),
        ),
      );

  // Everything in the banner is read from /health - nothing is hard-coded.
  Widget _banner() => FutureBuilder<Json?>(
        future: _health,
        builder: (context, snap) {
          final h = snap.data;
          String text;
          Color c;
          if (snap.connectionState != ConnectionState.done) {
            text = 'Connecting to backend…';
            c = muted;
          } else if (h == null) {
            text = 'Backend unreachable at $apiBase';
            c = danger;
          } else if (h['loaded'] != true) {
            text = '${h['error']}';
            c = danger;
          } else if ('${h['source']}'.contains('SYNTHETIC')) {
            text = 'SYNTHETIC DEMO DATA — not real ARGO observations (${h['profiles']} profiles). ${h['note'] ?? ''}'; // CHANGED (v2): shows why
            c = warn;
          } else {
            text = '${h['source']}  ·  ${h['profiles']} profiles, ${h['floats']} floats  ·  '
                '${'${h['time_min']}'.substring(0, 10)} to ${'${h['time_max']}'.substring(0, 10)}';
            c = accent;
          }
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            decoration: BoxDecoration(color: panel, border: Border(bottom: BorderSide(color: c.withOpacity(0.4)))),
            child: Row(children: [
              Icon(Icons.circle, size: 8, color: c),
              const SizedBox(width: 8),
              Expanded(child: Text(text, style: TextStyle(fontSize: 12, color: c, fontFamily: 'monospace'))),
            ]),
          );
        },
      );

  Widget _welcome() => Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Explore the ocean through conversation.', textAlign: TextAlign.center, style: TextStyle(fontSize: 30, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              const Text('Ask about ocean temperature and salinity from ARGO floats. Every number comes from retrieved observations, not from the language model.',
                  textAlign: TextAlign.center, style: TextStyle(color: muted)),
              const SizedBox(height: 24),
              Wrap(spacing: 12, runSpacing: 12, children: [
                for (final s in _suggestions)
                  InkWell(
                    onTap: () => _send(s.$2),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: 270,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(color: panel, borderRadius: BorderRadius.circular(12), border: Border.all(color: border)),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(s.$1, style: const TextStyle(fontSize: 11, color: primary, letterSpacing: 1)),
                        const SizedBox(height: 8),
                        Text(s.$2, style: const TextStyle(fontSize: 14)),
                      ]),
                    ),
                  ),
              ]),
            ]),
          ),
        ),
      );

  Widget _stream() => ListView.builder(
        controller: _scroll,
        padding: const EdgeInsets.all(16),
        itemCount: _turns.length,
        itemBuilder: (_, i) {
          final t = _turns[i];
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 900),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Align(
                  alignment: Alignment.centerRight,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 12, left: 48),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(color: const Color(0xFF0040CB), borderRadius: BorderRadius.circular(12)),
                    child: Text(t.question),
                  ),
                ),
                if (t.answer == null)
                  const Padding(padding: EdgeInsets.all(16), child: Row(children: [
                    SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
                    SizedBox(width: 12),
                    Text('Interpreting question and querying ARGO profiles…', style: TextStyle(color: muted)),
                  ]))
                else
                  AnswerCard(t.answer!),
                const SizedBox(height: 20),
              ]),
            ),
          );
        },
      );

  Widget _composer() => Container(
        color: surface,
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 900),
            child: TextField(
              controller: _input,
              onSubmitted: _send,
              decoration: InputDecoration(
                hintText: 'Ask an oceanographic question, e.g. average temperature at 500 m in the Arabian Sea in 2024…',
                filled: true,
                fillColor: panel,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: border)),
                suffixIcon: IconButton(icon: const Icon(Icons.send, color: primary), onPressed: () => _send()),
              ),
            ),
          ),
        ),
      );
}
