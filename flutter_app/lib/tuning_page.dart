// FILE: tuning_page.dart - NEW (v6) PAGE 3, Fine-tuning (course Unit III). Backend: tuning.py.
// Fine-tuning only improves how the model READS a question. It never changes the numbers, which engine.py computes exactly.
// The app can make the training data and measure a model. The training itself runs outside the app (it needs a GPU).
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'api.dart';
import 'api_extra.dart';
import 'glass.dart';

class TuningPage extends StatefulWidget {
  final ValueListenable<int> reload;
  const TuningPage({super.key, required this.reload});
  @override
  State<TuningPage> createState() => _TuningPageState();
}

class _TuningPageState extends State<TuningPage> {
  Json? _s;
  bool _busy = false;
  String _note = '';
  int _n = 1000;
  String _mode = 'rules';
  int _limit = 20;
  Json? _last; // result of the latest evaluation

  // ===== Manual fine-tuning state =====
  final _manualQuestion = TextEditingController();
  final _manualQuery = TextEditingController();
  final List<Map<String, String>> _manualPairs = [];

  @override
  void initState() {
    super.initState();
    widget.reload.addListener(_load);
    _load();
  }

  @override
  void dispose() {
    widget.reload.removeListener(_load);
    _manualQuestion.dispose();
    _manualQuery.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final s = await tuningStatus();
    if (mounted) setState(() => _s = s);
  }

  // ===== SECTION 1: actions =====
  Future<void> _generate() async {
    setState(() {
      _busy = true;
      _note = 'Generating $_n examples…';
    });
    final j = await tuningGenerate(_n);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _note = j['error'] != null ? '${j['error']}' : '${j['message']}';
      if (j['error'] == null) _s = j;
    });
  }

  Future<void> _evaluate() async {
    setState(() {
      _busy = true;
      _note = _mode == 'llm' ? 'Asking the model $_limit questions. A local model can need a few seconds per question…' : 'Scoring…';
    });
    final j = await tuningEvaluate(_mode, _limit);
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (j['error'] != null) {
        _note = '${j['error']}';
      } else {
        _note = '';
        _last = j;
        _s = j;
      }
    });
  }

  // ===== Manual pair actions =====
  void _addManualPair() {
    final q = _manualQuestion.text.trim();
    final a = _manualQuery.text.trim();
    if (q.isEmpty || a.isEmpty) return;
    setState(() {
      _manualPairs.add({'question': q, 'query': a});
      _manualQuestion.clear();
      _manualQuery.clear();
    });
  }

  void _removeManualPair(int idx) {
    setState(() => _manualPairs.removeAt(idx));
  }

  String _exportManualJsonl() {
    final lines = _manualPairs.map((p) => '{"input": "${_esc(p['question']!)}", "output": "${_esc(p['query']!)}"}');
    return lines.join('\n');
  }

  String _esc(String s) => s.replaceAll('\\', '\\\\').replaceAll('"', '\\"').replaceAll('\n', '\\n');

  // ===== SECTION 2: layout =====
  @override
  Widget build(BuildContext context) {
    final s = _s;
    if (s == null) return const Center(child: CircularProgressIndicator());
    if (s['error'] != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text('${s['error']}', textAlign: TextAlign.center, style: gBody(14, c: gErr))));
    }
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000),
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
          Text('MODEL ADAPTATION', style: gLabel(11)),
          const SizedBox(height: 6),
          Text('Fine-tuning', style: gHead(30)),
          const SizedBox(height: 12),
          _intro(),
          const SectionTitle('Current setup', Icons.memory),
          _status(s),
          const SectionTitle('1 · Generate training data (AI)', Icons.auto_fix_high),
          _generateCard(),
          const SectionTitle('2 · Manual training data', Icons.edit_note),
          _manualCard(),
          const SectionTitle('3 · Train outside the app', Icons.rocket_launch_outlined),
          _trainCard(),
          const SectionTitle('4 · Measure it', Icons.fact_check_outlined),
          _evalCard(),
          if (_last != null) ...[const SizedBox(height: 12), _resultCard(_last!)],
          const SectionTitle('Score history', Icons.timeline),
          _history(((s['runs'] as List?) ?? const []).cast<Json>()),
          const SectionTitle('Your laptop', Icons.laptop_chromebook),
          _hardware(),
        ]),
      ),
    );
  }

  Widget _intro() => GlassCard(
        glow: gCyan,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('What fine-tuning can and cannot do here', style: gHead(16)),
          const SizedBox(height: 8),
          Text('It teaches a small model to turn unusual wording into the exact structured query. It does not touch the science: the numbers always come from the Python engine and are verified.',
              style: gBody(13.5, c: gMuted)),
          const SizedBox(height: 8),
          Text('Keep a tuned model only if its score on the held-out questions (phrasings not in the training file) is higher than the base model.', style: gBody(13.5, c: gMuted)),
        ]),
      );

  Widget _status(Json s) {
    final tiles = [
      ('TRAINING ROWS', gNum(s['train_rows'] as num)),
      ('HELD-OUT QUESTIONS', gNum(s['val_rows'] as num)),
      ('ACTIVE MODEL', '${s['model']}'),
      ('MODEL REACHABLE', s['llm_available'] == true ? 'configured' : 'none'),
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
                Text(t.$1, style: gLabel(9.5, c: gMuted)),
                const SizedBox(height: 8),
                FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(t.$2, style: gHead(20, c: gCyan))),
              ]),
            ),
          ),
      ]);
    });
  }

  Widget _generateCard() => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(color: gCyan.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(8)),
              child: Text('AI-POWERED', style: gLabel(9, c: gCyan)),
            ),
          ]),
          const SizedBox(height: 10),
          Text('Automatically generates diverse question→query pairs for training. Makes train.jsonl and val.jsonl in backend/data/finetune. 20% of the questions use phrasings that never appear in training.', style: gBody(13.5, c: gMuted)),
          const SizedBox(height: 12),
          Wrap(spacing: 8, children: [
            for (final n in const [400, 1000, 2000])
              ChoiceChip(label: Text('$n'), selected: _n == n, selectedColor: gCyan.withValues(alpha: 0.25), onSelected: (_) => setState(() => _n = n)),
          ]),
          const SizedBox(height: 12),
          FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: gCyan, foregroundColor: gBg),
            onPressed: _busy ? null : _generate,
            icon: const Icon(Icons.auto_fix_high, size: 18),
            label: const Text('Generate training data'),
          ),
          if (_note.isNotEmpty && !_busy) ...[const SizedBox(height: 10), Text(_note, style: gLabel(11, c: gMuted))],
        ]),
      );

  // ===== NEW: Manual fine-tuning card =====
  Widget _manualCard() => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(color: gIndigo.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(8)),
              child: Text('MANUAL', style: gLabel(9, c: gIndigo)),
            ),
          ]),
          const SizedBox(height: 10),
          Text(
            'Type your own question→query pairs for fine-tuning. Use this when you know exactly which phrasings the model should learn. '
            'Add pairs below, then export to JSONL and append to your training file.',
            style: gBody(13.5, c: gMuted),
          ),
          const SizedBox(height: 16),
          // Question input
          Text('QUESTION (natural language)', style: gLabel(10, c: gMuted)),
          const SizedBox(height: 6),
          TextField(
            controller: _manualQuestion,
            style: gBody(13.5),
            maxLines: 2,
            minLines: 1,
            decoration: _inputDecor('e.g. What is the average temperature at 100m in the Arabian Sea in March 2024?'),
          ),
          const SizedBox(height: 12),
          // Query input
          Text('EXPECTED QUERY (structured JSON)', style: gLabel(10, c: gMuted)),
          const SizedBox(height: 6),
          TextField(
            controller: _manualQuery,
            style: gBody(13.5),
            maxLines: 3,
            minLines: 1,
            decoration: _inputDecor('e.g. {"stat":"mean","param":"temp","depth_m":100,"region":"arabian sea","months":[3],"year":2024}'),
          ),
          const SizedBox(height: 14),
          Row(children: [
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: gIndigo, foregroundColor: gBg),
              onPressed: _addManualPair,
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Add pair'),
            ),
            const SizedBox(width: 12),
            Text('${_manualPairs.length} pair${_manualPairs.length == 1 ? '' : 's'} added', style: gBody(13, c: gMuted)),
          ]),
          // List of added pairs
          if (_manualPairs.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              constraints: const BoxConstraints(maxHeight: 240),
              decoration: BoxDecoration(
                color: Colors.black.withValues(alpha: 0.25),
                borderRadius: BorderRadius.circular(14),
              ),
              child: ListView.separated(
                shrinkWrap: true,
                padding: const EdgeInsets.all(10),
                itemCount: _manualPairs.length,
                separatorBuilder: (_, __) => Divider(color: gLine.withValues(alpha: 0.4), height: 12),
                itemBuilder: (_, idx) {
                  final p = _manualPairs[idx];
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('Q: ${p['question']}', style: gBody(12.5, c: gText)),
                          const SizedBox(height: 2),
                          Text('A: ${p['query']}', style: gBody(11.5, c: gCyan)),
                        ]),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close, size: 16, color: gErr),
                        onPressed: () => _removeManualPair(idx),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
                        tooltip: 'Remove pair',
                      ),
                    ],
                  );
                },
              ),
            ),
            const SizedBox(height: 12),
            Row(children: [
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: gCyan, side: const BorderSide(color: gCyan)),
                onPressed: () {
                  final jsonl = _exportManualJsonl();
                  Clipboard.setData(ClipboardData(text: jsonl));
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('${_manualPairs.length} pairs copied as JSONL'),
                      backgroundColor: gCard,
                      behavior: SnackBarBehavior.floating,
                    ),
                  );
                },
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy as JSONL'),
              ),
              const SizedBox(width: 12),
              TextButton.icon(
                onPressed: () {
                  setState(() => _manualPairs.clear());
                },
                icon: const Icon(Icons.delete_outline, size: 16, color: gErr),
                label: Text('Clear all', style: gBody(13, c: gErr)),
              ),
            ]),
          ],
        ]),
      );

  InputDecoration _inputDecor(String hint) => InputDecoration(
        hintText: hint,
        hintStyle: gBody(12.5, c: gMuted.withValues(alpha: 0.5)),
        filled: true,
        fillColor: Colors.black.withValues(alpha: 0.3),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: gLine.withValues(alpha: 0.4))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: gLine.withValues(alpha: 0.4))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: gCyan)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      );

  static const _commands = '''# 1. Google Colab (free T4 GPU): LoRA-tune a small model on data/finetune/train.jsonl
#    input = the question, output = the JSON query   (libraries: peft, 4-bit quantization)
# 2. Export the tuned model as GGUF, then on your laptop:
ollama create floatchat-parser -f Modelfile     # Modelfile contains one line: FROM ./floatchat-parser.gguf
# 3. In backend/.env set:
OLLAMA_MODEL=floatchat-parser
PARSER=llm''';

  Widget _trainCard() => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Training needs a GPU, so it runs outside this app. LoRA trains only small adapter matrices, and 4-bit quantization makes the result small enough for a laptop.', style: gBody(13.5, c: gMuted)),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.35), borderRadius: BorderRadius.circular(14)),
            child: SelectableText(_commands, style: gLabel(11.5, c: gText)),
          ),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(onPressed: () => Clipboard.setData(const ClipboardData(text: _commands)), icon: const Icon(Icons.copy, size: 14), label: const Text('Copy')),
          ),
        ]),
      );

  Widget _evalCard() => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Runs the held-out questions through a parser and counts exact matches with the expected query.', style: gBody(13.5, c: gMuted)),
          const SizedBox(height: 12),
          Text('PARSER', style: gLabel(10, c: gMuted)),
          const SizedBox(height: 6),
          Wrap(spacing: 8, children: [
            for (final m in const [('rules', 'Rules (offline)'), ('fast', 'Fast (rules, then model)'), ('llm', 'Model only')])
              ChoiceChip(label: Text(m.$2), selected: _mode == m.$1, selectedColor: gCyan.withValues(alpha: 0.25), onSelected: (_) => setState(() => _mode = m.$1)),
          ]),
          const SizedBox(height: 12),
          Text('NUMBER OF QUESTIONS', style: gLabel(10, c: gMuted)),
          const SizedBox(height: 6),
          Wrap(spacing: 8, children: [
            for (final n in const [10, 20, 50])
              ChoiceChip(label: Text('$n'), selected: _limit == n, selectedColor: gCyan.withValues(alpha: 0.25), onSelected: (_) => setState(() => _limit = n)),
          ]),
          const SizedBox(height: 12),
          Row(children: [
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: gCyan, foregroundColor: gBg),
              onPressed: _busy ? null : _evaluate,
              icon: const Icon(Icons.play_arrow, size: 18),
              label: const Text('Run evaluation'),
            ),
            if (_busy) ...[const SizedBox(width: 12), const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))],
          ]),
          if (_note.isNotEmpty) ...[const SizedBox(height: 10), Text(_note, style: gLabel(11, c: gMuted))],
        ]),
      );

  Widget _resultCard(Json r) {
    final bad = ((r['failures'] as List?) ?? const []).cast<Json>();
    final acc = (r['accuracy'] as num).toDouble();
    return GlassCard(
      glow: acc >= 0.9 ? gCyan : gWarn,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('RESULT · ${r['mode']} · ${r['model']}', style: gLabel(10.5, c: gMuted)),
        const SizedBox(height: 6),
        Text('${(acc * 100).toStringAsFixed(1)}%  (${r['correct']} of ${r['n']} correct)', style: gHead(26, c: gCyan)),
        Text('${r['avg_ms']} ms per question', style: gBody(13, c: gMuted)),
        if (bad.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text('Examples it got wrong', style: gHead(14)),
          for (final b in bad)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text('• ${b['question']}  →  ${b['got'] is String ? b['got'] : 'different query'}', style: gBody(12.5, c: gMuted)),
            ),
        ],
      ]),
    );
  }

  Widget _history(List<Json> runs) {
    if (runs.isEmpty) return GlassCard(child: Text('No runs yet. Run an evaluation above. Run it again after changing OLLAMA_MODEL to compare the base model with the tuned one.', style: gBody(13.5, c: gMuted)));
    return GlassCard(
      child: Column(children: [
        for (final r in runs)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Row(children: [
              Expanded(child: Text('${r['mode']} · ${r['model']}', style: gBody(13), overflow: TextOverflow.ellipsis)),
              Text('${((r['accuracy'] as num) * 100).toStringAsFixed(1)}%', style: gHead(14, c: gCyan)),
              const SizedBox(width: 12),
              Text('${r['avg_ms']} ms', style: gLabel(10.5, c: gMuted)),
            ]),
          ),
      ]),
    );
  }

  Widget _hardware() => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Intel Core Ultra 7 with Arc graphics', style: gHead(15)),
          const SizedBox(height: 8),
          Text('• Run models with Ollama: llama3.2 (3B), or qwen2.5:1.5b if it feels slow. Expect roughly 5–15 tokens per second on the CPU (an estimate).', style: gBody(13, c: gMuted)),
          const SizedBox(height: 4),
          Text('• Training on this laptop is not practical. Use free Google Colab for the LoRA step.', style: gBody(13, c: gMuted)),
          const SizedBox(height: 4),
          Text('• PARSER=fast answers clear questions in milliseconds without the model.', style: gBody(13, c: gMuted)),
        ]),
      );
}
