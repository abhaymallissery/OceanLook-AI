// FILE: api.dart - talks to the FastAPI backend. CHANGED (v2): new fields + session id for conversation memory.
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Set with: flutter run --dart-define=API_BASE=http://10.0.2.2:8000  (Android emulator -> host machine)
const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://localhost:8000');

// ===== SECTION 1: settings and types =====
// CHANGED (v2): one id per app run; the backend uses it to remember earlier questions (follow-ups like "and for salinity?").
final sessionId = 'app-${DateTime.now().millisecondsSinceEpoch}';

typedef Json = Map<String, dynamic>;

class Answer {
  final String status, message, explanation;
  final Json? interpretation, result;
  // CHANGED (v2): synthetic flag, RAG passages, agent steps, extra agent results, which parser answered
  final bool synthetic;
  final List<Json> docs, extra;
  final List<String> steps;
  final String parser;
  Answer({required this.status, this.message = '', this.explanation = '', this.interpretation, this.result, this.synthetic = false,
      this.docs = const [], this.steps = const [], this.extra = const [], this.parser = ''});

  factory Answer.fromJson(Json j) => Answer(
        status: j['status'] as String? ?? 'error',
        message: j['message'] as String? ?? '',
        explanation: j['explanation'] as String? ?? '',
        interpretation: j['interpretation'] as Json?,
        result: j['result'] as Json?,
        synthetic: j['synthetic'] == true,
        docs: ((j['docs'] as List?) ?? []).cast<Json>(),
        steps: ((j['steps'] as List?) ?? []).cast<String>(),
        extra: ((j['extra'] as List?) ?? []).cast<Json>(),
        parser: j['parser_used'] as String? ?? '',
      );
}

// ===== SECTION 2: ask - POST /ask, never throws; failures become an "error" answer the UI can show =====
Future<Answer> ask(String question) async {
  try {
    final r = await http
        .post(Uri.parse('$apiBase/ask'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'question': question, 'session_id': sessionId}))
        .timeout(const Duration(seconds: 90));
    if (r.statusCode != 200) return Answer(status: 'error', message: 'Backend returned HTTP ${r.statusCode}.');
    return Answer.fromJson(jsonDecode(utf8.decode(r.bodyBytes)) as Json);
  } catch (e) {
    return Answer(status: 'error', message: 'Cannot reach the backend at $apiBase ($e).');
  }
}

// ===== SECTION 3: health - what data is loaded (the top banner reads only from this) =====
Future<Json?> health() async {
  try {
    final r = await http.get(Uri.parse('$apiBase/health')).timeout(const Duration(seconds: 10));
    return jsonDecode(r.body) as Json;
  } catch (_) {
    return null;
  }
}
